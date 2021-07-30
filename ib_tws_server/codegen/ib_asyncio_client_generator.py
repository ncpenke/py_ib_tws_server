from __future__ import annotations
from ib_tws_server.asyncio.ib_client_base import IBClientBase
from ib_tws_server.codegen.generator_utils import GeneratorUtils
from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
import inspect
from subprocess import call

class IBAsyncioClientGenerator:

    @staticmethod
    def generate(filename):
        def response_is_list(d: ApiDefinition):
            return d.has_done_flag or d.done_method is not None

        def forward_method_parameters_dict_style(params: List[inspect.Parameter]) -> str:
            return ",".join([ f"{v.name} = {v.name}" for v in params ])

        def request_return_type(d: ApiDefinition, is_subscription: bool):
            if is_subscription:
                return "Subscription"
            elif (d.callback_methods is not None):
                return GeneratorUtils.response_type(d)
            else:
                return "None"

        def query_response_type(d: ApiDefinition):
            ret = request_return_type(d, False)
            if response_is_list(d):
                ret = f"List[{ret}]"
            return ret

        def streaming_callback_type(d: ApiDefinition):
            return f"Callable[[{GeneratorUtils.streaming_type(d)}],None]"

        def request_state_member_name(d: ApiDefinition):
            return f"_req_state"       

        def subscription_member_name(d: ApiDefinition):
            return f"_subscriptions"       

        def request_id(d: ApiDefinition, m: Callable):
            if not d.uses_req_id:
                return f"'{d.request_method.__name__}'"
            else:
                return GeneratorUtils.req_id_param_name(m)

        def current_request_state(d: ApiDefinition, m: Callable):
            return f"self.{request_state_member_name(d)}[{request_id(d, m)}]"

        def current_subscription(d: ApiDefinition, m: Callable):
            return f"self.{subscription_member_name(d)}[{request_id(d, m)}]"

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

            return f"{current_subscription(d,m)}= Subscription(streaming_cb, self.{d.cancel_method.__name__}, {GeneratorUtils.req_id_param_name(d.request_method)}, asyncio.get_running_loop())"

        def bind_method(func: callable) -> str:
            return f"functools.partial(EClient.{func.__name__},{GeneratorUtils.forward_parameters(func)})"

        def bind_request_method(d: ApiDefinition, param_values: List[str], is_subscription: bool) -> str:
            param_values.insert(0,f"EClient.{d.request_method.__name__}")
            return f"functools.partial({','.join(param_values)})"

        def async_request_method(d: ApiDefinition, is_subscription: bool):
            return_type = request_return_type(d, is_subscription)
            signature = GeneratorUtils.signature(d.request_method).replace(return_annotation=return_type)
            params = list(signature.parameters.values())
            method_name = d.request_method.__name__
            param_values = [ p.name if p.name != d.subscription_flag_name else f"{d.subscription_flag_value}" for p in params ]
            
            if is_subscription and d.subscription_flag_name is not None:
                method_name = f"{method_name}AsSubscription"
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
        self._writer.queue.put({bind_request_method(d, param_values, is_subscription)})
        return ret"""
            if d.callback_methods is not None or d.done_method is not None:
                return f"""

    async def {method_name}{signature}:
        {GeneratorUtils.doc_string(d.request_method)}
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        def cb(res: {request_return_type(d, is_subscription)}):
            loop.call_soon_threadsafe(future.set_result, res)
        {init_request_id(d, d.request_method)}
        with self._lock:
            {init_callback(d, d.request_method, 'cb')}
        self._writer.queue.put({bind_request_method(d, param_values, is_subscription)})
        return (await future)"""

            else:
                return f"""

    async def {method_name}{signature}:
        {GeneratorUtils.doc_string(d.request_method)}
        {init_request_id(d, d.request_method)}
        self._writer.queue.put({bind_request_method(d, param_values, is_subscription)})
        return None"""

        def response_instance(d: ApiDefinition, m: Callable):
            return f"{GeneratorUtils.response_type(d)}({m.__name__} = {GeneratorUtils.callback_type(m)}({forward_method_parameters_dict_style(GeneratorUtils.data_class_members(d, [m], False))}))"

        def streaming_instance(d: ApiDefinition, m: Callable):
            return f"{GeneratorUtils.streaming_type(d)}({m.__name__} = {GeneratorUtils.callback_type(m)}({forward_method_parameters_dict_style(GeneratorUtils.data_class_members(d, [m], True))}))"

        def update_response(d: ApiDefinition, m:Callable):
            if response_is_list(d):
                return f"""
            if {request_id(d, m)} in self._req_state:
                req_state = {current_request_state(d, m)}
                if req_state.response is None:
                    req_state.response = [] 
                req_state.response.append({response_instance(d, m)})"""
            else:
                return f"""
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
            elif not response_is_list(d):
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

        def cancel_method(d: ApiDefinition):
            return f"""

    def {GeneratorUtils.method_declaration(d.cancel_method)}:
        {GeneratorUtils.doc_string(d.cancel_method)}
        self.cancel_request({request_id(d,d.cancel_method)})
        self._writer.queue.put({bind_method(d.cancel_method)})"""

        with open(filename, "w") as f:
            f.write(f"""
import asyncio
from collections import defaultdict
import functools
from ib_tws_server.asyncio.ib_client_base import *
from ib_tws_server.gen.client_responses import *
from ib_tws_server.ib_imports import *
from typing import Callable, Dict, List, Tuple

class IBAsyncioClient(IBClientBase):
    def __init__(self):
        IBClientBase.__init__(self)
"""
            )
            for d in ApiDefinitionManager.REQUEST_DEFINITIONS:
                if d.request_method is not None:
                    if d.subscription_flag_name is not None:
                        f.write(async_request_method(d, False))
                        f.write(async_request_method(d, True))
                    else:
                        f.write(async_request_method(d, d.is_subscription))
                    if d.callback_methods is not None:
                        for m in d.callback_methods:
                            f.write(callback_method(d, m))
                        if d.done_method is not None:
                            f.write(done_method(d))
                    if d.cancel_method is not None:
                        f.write(cancel_method(d))
