from ib_tws_server.codegen.generator_utils import GeneratorUtils
from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
import inspect

def forward_method_parameters_dict_style(params: List[inspect.Parameter]) -> str:
    return ",".join([ f"{v.name} = {v.name}" for v in params ])

def streaming_callback_type(d: ApiDefinition):
    return f"Callable[[{GeneratorUtils.streaming_type(d)}],None]"

def request_state_member_name(d: ApiDefinition):
    return f"_req_state"       

def subscription_member_name(d: ApiDefinition):
    return f"_subscriptions"       

def response_instance(d: ApiDefinition, m: Callable):
    return f"{GeneratorUtils.response_type(d)}({m.__name__} = {GeneratorUtils.callback_type(m)}({forward_method_parameters_dict_style(GeneratorUtils.data_class_members(d, [m], False))}))"

def streaming_instance(d: ApiDefinition, m: Callable):
    return f"{GeneratorUtils.streaming_type(d)}({m.__name__} = {GeneratorUtils.callback_type(m)}({forward_method_parameters_dict_style(GeneratorUtils.data_class_members(d, [m], True))}))"

def request_id(d: ApiDefinition, m: Callable):
    if not d.uses_req_id:
        return f"'{d.request_method.__name__}'"
    else:
        return GeneratorUtils.req_id_param_name(m)

def current_request_state(d: ApiDefinition, m: Callable):
    return f"self.{request_state_member_name(d)}[{request_id(d, m)}]"

def bind_method(d: ApiDefinition, m: Callable, param_values: List[str]) -> str:
    param_values[0] = f"self._client.{m.__name__}"
    return f"functools.partial({','.join(param_values)})"

class AsyncioClientGenerator:
    @staticmethod
    def generate(filename):
        def init_callback(d: ApiDefinition, m: Callable, cb: str):
            if d.callback_methods is not None or d.done_method is not None:
                return f"{current_request_state(d,m)}.{cb} = {cb}"
            return ""

        def init_request_id(d: ApiDefinition, u: Callable):
            if d.uses_req_id:
                return f"{GeneratorUtils.req_id_param_name(d.request_method)} = self.next_request_id()"
            else:
                return ""

        def init_subscription(d: ApiDefinition):
            if d.cancel_method is None:
                raise RuntimeError(f"Request does not support cancellation {d.request_method.__name__}")

            current_subscription = f"self.{subscription_member_name(d)}[{request_id(d, d.request_method)}]"

            return f"{current_subscription}= Subscription(streaming_cb, self.__{d.cancel_method.__name__}, {GeneratorUtils.req_id_param_name(d.request_method)}, asyncio.get_running_loop())"

        def async_request_method(d: ApiDefinition, is_subscription: bool):
            return_type = f"Union[{GeneratorUtils.request_return_type(d, is_subscription)},Error]"
            signature = GeneratorUtils.signature(d.request_method).replace(return_annotation=return_type)
            params = list(signature.parameters.values())
            method_name = GeneratorUtils.request_method_name(d, d.request_method, is_subscription)
            param_values = [ p.name if p.name != d.subscription_flag_name else f"{d.subscription_flag_value}" for p in params ]
            
            if d.uses_req_id:
                del params[1]
            if is_subscription:
                params.insert(1, inspect.Parameter('streaming_cb', kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=streaming_callback_type(d)))
            if d.subscription_flag_name is not None:
                params = [ p for p in params if p.name != d.subscription_flag_name ]
            signature = signature.replace(parameters=params)

            if is_subscription:
                return f"""

    async def {method_name}{signature}:
        {GeneratorUtils.doc_string(d.request_method)}
        {init_request_id(d, d.request_method)}
        ret: Subscription = None
        with self._lock:
            ret = {init_subscription(d)}
        self._writer.queue.put({bind_method(d, d.request_method, param_values)})
        return ret"""
            if d.callback_methods is not None or d.done_method is not None:
                return f"""

    async def {method_name}{signature}:
        {GeneratorUtils.doc_string(d.request_method)}
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        def cb(res: {GeneratorUtils.request_return_type(d, is_subscription)}):
            loop.call_soon_threadsafe(future.set_result, res)
        {init_request_id(d, d.request_method)}
        with self._lock:
            {init_callback(d, d.request_method, 'cb')}
        self._writer.queue.put({bind_method(d, d.request_method, param_values)})
        return (await future)"""

            else:
                return f"""

    async def {method_name}{signature}:
        {GeneratorUtils.doc_string(d.request_method)}
        {init_request_id(d, d.request_method)}
        self._writer.queue.put({bind_method(d, d.request_method, param_values)})
        return None"""

        def cancel_method(d: ApiDefinition):
            return f"""

    def __{GeneratorUtils.method_declaration(d.cancel_method)}:
        {GeneratorUtils.doc_string(d.cancel_method)}
        self.cancel_request({request_id(d,d.cancel_method)})
        self._writer.queue.put({bind_method(d, d.cancel_method, list(GeneratorUtils.signature(d.cancel_method).parameters))})"""

        with open(filename, "w") as f:
            f.write(f"""
import asyncio
import functools
from collections import defaultdict
from ib_tws_server.asyncio.error import Error
from ib_tws_server.asyncio.ib_writer import IBWriter
from ib_tws_server.asyncio.request_state import *
from ib_tws_server.gen.client_responses import *
from ib_tws_server.gen.asyncio_wrapper import *
from ib_tws_server.ib_imports import *
from threading import Lock, Thread
from typing import Callable, Dict, List, Tuple, Union

class AsyncioClient():
    _lock: Lock
    _req_state: Dict[str, RequestState]
    _subscriptions: Dict[int, Subscription]
    _wrapper: AsyncioWrapper
    _client: EClient

    def __init__(self):
        self._lock = Lock()
        self._current_request_id = 0
        self._req_state = defaultdict(RequestState)
        self._subscriptions = defaultdict(Subscription)

        self._wrapper = AsyncioWrapper(self._lock, self._req_state, self._subscriptions)
        self._client = EClient(self._wrapper)
        self._writer = IBWriter(self._client)
        self._wrapper._writer = self._writer

    def run(self):
        self._writer.start()
        self._client.run()

    def next_request_id(self):
        with self._lock:
            self._current_request_id += 1
            return self._current_request_id

    def disconnect(self, clean=False):
        self._wrapper._expecting_disconnect = clean
        return self._client.disconnect()

    def cancel_request(self, id: RequestId):
        response_cb = None
        with self._lock:
            if id in self._req_state:
                response_cb = self._req_state[id].cb
                del self._req_state[id]
            if id in self._subscriptions:
                del self._subscriptions[id]
        if response_cb is not None:
            response_cb(None)

    def start(self, host: str, port: int, client_id: int):
        self._client.connect(host, port, client_id)
        thread = Thread(target = self.run)
        thread.start()
        setattr(thread, "_thread", thread)

    def error(self, reqId:int, errorCode:int, errorString:str):
        logger.error(f'Response error {{reqId}} {{errorCode}} {{errorString}}')
        cb:Callable = None
        with self._lock:
            if reqId in self._req_state:
                cb = self._req_state[reqId].cb
                del self._req_state[reqId]
            if reqId in self._subscriptions:
                del self._subscriptions[reqId]
        if cb is not None:
            cb(None)

    def active_request_count(self):
        with self._lock:
            return len(self._req_state) 

    def active_subscription_count(self):
        with self._lock:
            return len(self._subscriptions) 
"""
            )
            for d in REQUEST_DEFINITIONS:
                if d.request_method is not None:
                    if d.subscription_flag_name is not None:
                        f.write(async_request_method(d, False))
                        f.write(async_request_method(d, True))
                    else:
                        f.write(async_request_method(d, d.is_subscription))
                    if d.cancel_method is not None and (d.is_subscription or d.subscription_flag_name is not None):
                        f.write(cancel_method(d))

class AsyncioWrapperGenerator:
    @staticmethod
    def generate(filename):
        def update_response(d: ApiDefinition, m:Callable):
            if GeneratorUtils.response_is_list(d):
                return f"""
            if {request_id(d, m)} in self._req_state:
                req_state = {current_request_state(d, m)}
                if req_state.response is None:
                    req_state.response = [] 
                req_state.response.append({response_instance(d, m)})"""
            else:
                return f"""
            if {request_id(d, m)} in self._req_state:
                req_state = {current_request_state(d, m)}
                if req_state is not None:
                    req_state.response = {response_instance(d, m)}"""

        def call_response_cb(d: ApiDefinition, m: Callable):
            if d.callback_methods is not None:
                return f"self.call_response_cb({request_id(d,m)})"
            else:
                return ""

        def call_response_cb_if_done(d: ApiDefinition, m: Callable):
            if d.has_done_flag:
                return f"""
        if (done):
            {call_response_cb(d, m)}"""
            elif not GeneratorUtils.response_is_list(d):
                return f"""
        {call_response_cb(d,m)}"""
            else:
                return ""

        def callback_method(d: ApiDefinition, m: Callable):
            if d.subscription_flag_name is not None:
                return f"""

    def {GeneratorUtils.method_declaration(m)}:
        {GeneratorUtils.doc_string(m)}
        is_subscription: bool = False
        with self._lock:
            is_subscription = {request_id(d, m)} in self._subscriptions
            {update_response(d, m)}
        if is_subscription:
            self.call_streaming_cb({request_id(d,m)}, {streaming_instance(d,m)})
            return
        {call_response_cb_if_done(d, m)}"""

            elif not d.is_subscription:
                return f"""
    def {GeneratorUtils.method_declaration(m)}:
        {GeneratorUtils.doc_string(m)}
        with self._lock:
            {update_response(d, m)}
        {call_response_cb_if_done(d, m)}"""
            else:
                return f"""

    def {GeneratorUtils.method_declaration(m)}:
        {GeneratorUtils.doc_string(m)}
        self.call_streaming_cb({request_id(d,m)}, {streaming_instance(d,m)})"""

        def done_method(d: ApiDefinition):
            return f"""

    def {GeneratorUtils.method_declaration(d.done_method)}:
        {GeneratorUtils.doc_string(d.done_method)}
        {call_response_cb(d,d.done_method)}"""
        with open(filename, "w") as f:
            f.write(f"""
import asyncio
import functools
from ib_tws_server.asyncio.error import Error
from ib_tws_server.asyncio.ib_writer import IBWriter
from ib_tws_server.asyncio.request_state import *
from ib_tws_server.gen.client_responses import *
from ib_tws_server.ib_imports import *
from threading import Lock, Thread
from typing import Callable, Dict, List, Tuple

class AsyncioWrapper(EWrapper):
    _lock: Lock
    _req_state: Dict[str, RequestState]
    _subscriptions: Dict[int, Subscription]
    _expecting_disconnect: bool
    _writer: IBWriter

    def __init__(self, lock: Lock, req_state: Dict[str, RequestState], subscriptions: Dict[int, Subscription]):
        self._lock = lock
        self._req_state = req_state
        self._subscriptions = subscriptions
        EWrapper.__init__(self)
        self._expecting_disconnect = False

    def connectionClosed(self):
        if self._expecting_disconnect:
            # Wake up writer
            self._writer.queue.put(lambda *a, **k: None)
        else:
            raise RuntimeError("Unexpected disconnect")

    def call_response_cb(self, id: RequestId, res=None):
        cb = None
        with self._lock:
            if not id in self._req_state:
                return

            s = self._req_state[id]
            cb = s.cb
            if res is None:
                res = s.response
            del self._req_state[id]

        if cb is not None:
            cb(res)

    def error(self, reqId: TickerId, errorCode: int, errorString: str):
        cb = None
        if reqId is not None:
            with self._lock:
                if reqId in self._req_state:
                    s = self._req_state[reqId]
                    cb = s.cb
                    del self._req_state[reqId]
        if cb is not None:
            cb(Error(errorString, errorCode))
        else:
            super().error(reqId, errorCode, errorString)
        
    def call_streaming_cb(self, id: RequestId, res: any):
        cb = None
        loop = None
        with self._lock:
            if id in self._subscriptions:
                s = self._subscriptions[id]
                cb = s.streaming_cb
                loop = s.loop
        if loop is not None:
            loop.call_soon_threadsafe(cb, res)
""")
            for d in REQUEST_DEFINITIONS:
                if d.request_method is not None:
                    if d.callback_methods is not None:
                        for m in d.callback_methods:
                            f.write(callback_method(d, m))
                        if d.done_method is not None:
                            f.write(done_method(d))
