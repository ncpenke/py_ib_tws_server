from ib_wrapper.asyncio.ib_client_base import IBClientBase
from subprocess import call
from ib_wrapper.codegen.generator_utils import GeneratorUtils
from ib_wrapper.api_definition import *
from ib_wrapper.codegen.generator_utils import *
import inspect

class IBAsyncioClientGenerator:
    @staticmethod
    def generate(filename):
        def response_is_list(d: ApiDefinition):
            return d.has_done_flag or d.done_method is not None

        def request_id_parameter_name(u: Callable):
            return list(inspect.signature(u).parameters.values())[1].name

        def forward_method_parameters_dict_style(params: List[inspect.Parameter]) -> str:
            return ",".join([ f"{v.name} = {v.name}" for v in params ])

        def update_response_type(d: ApiDefinition):
            ret = GeneratorUtils.response_type(d)
            if response_is_list(d):
                ret = f"List[{ret}]"
            return ret

        def streaming_callback_type(d: ApiDefinition):
            return f"Callable[[{GeneratorUtils.streaming_type(d)}],None]"

        def request_return_type(d: ApiDefinition):
            updateResponseType = None
            streamingResponseType = None
            if (d.update_methods is not None):
                updateResponseType = update_response_type(d)
            if (d.stream_methods is not None):
                streamingResponseType = "Subscription"

            if streamingResponseType is not None and updateResponseType is not None:
                return f"Tuple[{updateResponseType}, Subscription]"
            return streamingResponseType if streamingResponseType is not None else updateResponseType
        def request_state_member_name(d: ApiDefinition):
            return f"_req_state"       

        def subscription_member_name(d: ApiDefinition):
            return f"_subscriptions"       

        def request_id(d: ApiDefinition, m: Callable):
            if d.req_id_names is None:
                return f"'{d.request_method.__name__}'"
            else:
                return request_id_parameter_name(m)

        def current_request_state(d: ApiDefinition, m: Callable):
            return f"self.{request_state_member_name(d)}[{request_id(d, m)}]"

        def current_subscription(d: ApiDefinition, m: Callable):
            return f"self.{subscription_member_name(d)}[{request_id(d, m)}]"

        def request_return_instance(d: ApiDefinition, m: callable):
            if (d.update_methods is not None and d.stream_methods is not None):
                return f"self.get_subscription_and_response({request_id(d, m)})"
            elif d.update_methods is not None:
                return f"{current_request_state(d,m)}.response"
            else:
                return f"{current_subscription(d,m)}"

        def init_callback(d: ApiDefinition, m: Callable, cb: str):
            if d.update_methods is not None or d.done_method is not None:
                return f"{current_request_state(d,m)}.{cb} = {cb}"
            return ""

        def init_request_id(d: ApiDefinition, u: Callable):
            if d.req_id_names is not None:
                return f"{request_id_parameter_name(d.request_method)} = self.next_request_id()"
            else:
                return ""
    
        def init_subscription(d: ApiDefinition):
            if d.stream_methods is None:
                return ""

            if d.cancel_method is None:
                raise RuntimeError(f"Request does not support cancellation {d.request_method.__name__}")

            return f"{current_subscription(d,m)}= Subscription(streaming_cb, self.{d.cancel_method.__name__}, {request_id_parameter_name(d.request_method)})"

        def async_request_method(d: ApiDefinition):
            return_type = request_return_type(d)
            signature = inspect.signature(d.request_method).replace(return_annotation=return_type)
            params = list(signature.parameters.values())
            if d.req_id_names is not None:
                params = [ k for k in signature.parameters.values() if k.name not in d.req_id_names ]
            if d.stream_methods is not None:
                params.insert(1, inspect.Parameter('streaming_cb', kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=streaming_callback_type(d)))
            signature = signature.replace(parameters=params)
            if d.update_methods is not None or d.done_method is not None:
                return f"""

    async def {d.request_method.__name__}{signature}:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        def cb(res: {request_return_type(d)}):
            loop.call_soon_threadsafe(future.set_result, res)
        {init_request_id(d, d.request_method)}
        with self._lock:
            {init_callback(d, d.request_method, 'cb')}
            {init_subscription(d)}
        self._writer.queue.put({bind_method(d.request_method)})
        return (await future)"""
            elif d.stream_methods is not None:
                return f"""

    async def {d.request_method.__name__}{signature}:
        {init_request_id(d, d.request_method)}
        ret: Subscription = None
        with self._lock:
            ret = {init_subscription(d)}
        self._writer.queue.put({bind_method(d.request_method)})
        return ret"""
            else:
                return f"""

    async def {d.request_method.__name__}{signature}:
        {init_request_id(d, d.request_method)}
        self._writer.queue.put({bind_method(d.request_method)})
        return None"""


        def bind_method(func: callable) -> str:
            return f"functools.partial(EClient.{func.__name__},{GeneratorUtils.forward_parameters(func)})"

        def response_instance(d: ApiDefinition, m: Callable):
            return f"{GeneratorUtils.response_type(d)}({forward_method_parameters_dict_style(GeneratorUtils.data_class_members(d, [m], False))})"

        def streaming_instance(d: ApiDefinition, m: Callable):
            return f"{GeneratorUtils.streaming_type(d)}({forward_method_parameters_dict_style(GeneratorUtils.data_class_members(d, [m], True))})"

        def update_response(d: ApiDefinition, m:Callable):
            if response_is_list(d):
                return f"""
            _req_state ={current_request_state(d, m)}
            if _req_state.response is None:
                _req_state.response = [] 
            _req_state.response.append({response_instance(d, m)})"""
            return f"""
            {current_request_state(d, m)}.response = {response_instance(d, m)}"""

        def call_response_cb(d: ApiDefinition, m: Callable):
            if d.update_methods is not None and d.stream_methods is not None:
                return f"self.call_response_cb({request_id(d,m)}, self.get_subscription_and_response_no_lock({request_id(d,m)}))"
            elif d.update_methods is not None:
                return f"self.call_response_cb({request_id(d,m)})"
            else:
                return ""

        def call_response_cb_if_done(d: ApiDefinition, m: Callable):
            if d.has_done_flag:
                return f"""
        if (done):
            {call_response_cb(d, m)}"""
            elif not response_is_list(d):
                return f"""
        {call_response_cb(d,m)}"""
            else:
                return ""

        def response_callback(d: ApiDefinition, m: Callable):
            return f"""

    def {GeneratorUtils.method_declaration(m)}:
        with self._lock:
            {update_response(d, m)}
        {call_response_cb_if_done(d, m)}"""

        def streaming_callback(d: ApiDefinition, m: Callable):
            return f"""

    def {GeneratorUtils.method_declaration(m)}:
        self.call_streaming_cb({request_id(d,m)}, {streaming_instance(d,m)})"""

        def done_method(d: ApiDefinition):
            return f"""
    def {GeneratorUtils.method_declaration(d.done_method)}:
        {call_response_cb(d,m)}"""

        def cancel_method(d: ApiDefinition):
            return f"""
    def {GeneratorUtils.method_declaration(d.cancel_method)}:
        self.cancel_request({request_id(d,m)})
        self._writer.queue.put({bind_method(d.cancel_method)})"""

        with open(filename, "w") as f:
            f.write(f"""
import asyncio
from collections import defaultdict
import functools
from ibapi.client import *
from ibapi.wrapper import *
from ib_wrapper.asyncio.ib_client_base import *
from ib_wrapper.gen.ib_client_responses import *
from typing import Callable, Dict, List, Tuple

class IBAsyncioClient(IBClientBase):
    def __init__(self):
        IBClientBase.__init__(self)
"""
            )
            for d in ApiDefinitionManager.DEFINITIONS:
                if d.request_method is not None:
                    f.write(async_request_method(d))
                    if d.update_methods is not None:
                        for m in d.update_methods:
                            f.write(response_callback(d, m))
                        if d.done_method is not None:
                            f.write(done_method(d))
                    if d.stream_methods is not None:
                        for m in d.stream_methods:
                            f.write(streaming_callback(d, m))
                    if d.cancel_method is not None:
                        f.write(cancel_method(d))
