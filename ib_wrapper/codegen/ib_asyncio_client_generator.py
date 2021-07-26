from ib_wrapper.asyncio.ib_client_base import IBClientBase
from subprocess import call
from ib_wrapper.codegen.generator_utils import GeneratorUtils
from ib_wrapper.api_definition import *
from ib_wrapper.codegen.generator_utils import *
import inspect

class IBAsyncioClientGenerator:
    @staticmethod
    def generate(filename):
        def async_request_method_declaration(d: ApiDefinition):
            response_type = GeneratorUtils.response_type_for_definition(d)
            signature = inspect.signature(d.request_method).replace(return_annotation=response_type)
            if d.req_id_names is not None:
                params = []
                for k,v in signature.parameters.items():
                    if k not in d.req_id_names:
                        params.append(v)
                signature = signature.replace(parameters=params)
            return f"""

    async def {d.request_method.__name__}{signature}:"""

        def async_request_method_definition(d: ApiDefinition):
            return f"""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        def cb(res: {GeneratorUtils.response_type_for_definition(d)}):
            loop.call_soon_threadsafe(asyncio.Future.set_result, future, res)
        {request_id_assignment(d, d.request_method)}
        with self._lock:
            {callback_state_assignment(d, 'cb')}
        self._writer.queue.put({bind_request_method(d.request_method)})
        return (await future)"""

        def has_multiple_updates(d: ApiDefinition):
            return d.has_done_flag or d.done_method is not None

        def async_method(d: ApiDefinition):
            return f"{async_request_method_declaration(d)}{async_request_method_definition(d)}"

        def request_state_name(d: ApiDefinition):
            if (d.request_method is None):
                return None
            return f"_cb_{d.request_method.__name__}"
            
        def request_state_type(d: ApiDefinition):
            if (d.request_method is None):
                return None
            response_type = GeneratorUtils.response_type_for_definition(d)
            if (d.req_id_names is None):
                return f"GlobalRequestState[{response_type}]"
            else:
                return f"SingleRequestState[{response_type}]"

        def request_state_initial_value(d: ApiDefinition):
            if (d.request_method is None):
                return None
            response_type = GeneratorUtils.response_type_for_definition(d)
            if (d.req_id_names is None):
                return f"GlobalRequestState[{response_type}]()"
            else:
                return f"{{}}"

        def request_id_parameter_name(u: Callable):
            return list(inspect.signature(u).parameters.values())[1].name

        def callback_state_assignment(d: ApiDefinition, cb: str):
            if (d.req_id_names is None):
                return f"self.{request_state_name(d)}.cbs.append({cb})"
            else:
                return f"self.{request_state_name(d)}[{request_id_parameter_name(d.request_method)}] = SingleRequestCallbackState({cb})"

        def request_id_assignment(d: ApiDefinition, u: Callable):
            if (d.req_id_names is not None):
                return f"{request_id_parameter_name(d.request_method)} = self.next_request_id()"
            else:
                return ""

        def streaming_request_state_name(d: ApiDefinition, u: Callable):
            return f"_cb_{u.__name__}"

        def streaming_request_state_type(d: ApiDefinition, u: Callable):
            response_type = GeneratorUtils.response_type_for_stream_method(d, u)
            if (d.req_id_names is None):
                return f"GlobalStreamingRequestState[{response_type}]"
            else:
                return f"SingleStreamingRequestState[{response_type}]"

        def streaming_request_state_initial_value(d: ApiDefinition, u: Callable):
            response_type = GeneratorUtils.response_type_for_stream_method(d, u)
            if (d.req_id_names is None):
                return f"{{}}"
            else:
                return f"[]"

        def declare_callback_containers():
            ret = ""
            for d in ApiDefinitionManager.DEFINITIONS:
                if d.update_methods is not None:
                    name = request_state_name(d)
                    t = request_state_type(d)
                    ret = ret + f""" 
    {name}: {t}"""
                if d.stream_methods is not None:
                    for m in d.stream_methods:
                        name = streaming_request_state_name(d, m)
                        t = streaming_request_state_type(d, m)
                        ret = ret + f"""
    {name}: {t}"""
            return ret

        def initialize_callback_containers():
            ret = ""
            for d in ApiDefinitionManager.DEFINITIONS:
                if d.update_methods is not None:
                    name = request_state_name(d)
                    i = request_state_initial_value(d)
                    ret = ret + f""" 
        self.{name} = {i}"""
                if d.stream_methods is not None:
                    for m in d.stream_methods:
                        name = streaming_request_state_name(d, m)
                        i = streaming_request_state_initial_value(d, m)
                        ret = ret + f"""
        self.{name} = {i}"""
            return ret

        def bind_request_method(func: callable) -> str:
            return f"functools.partial(EClient.{func.__name__},{GeneratorUtils.forward_parameters(func)})"

        def request_id_update_method(d: ApiDefinition, u: Callable):
            pass

        def request_id_done_method(d: ApiDefinition, u: Callable):
            pass

        def request_id_streaming_method(d: ApiDefinition, u: Callable):
            pass

        def global_single_update_method(d: ApiDefinition):
            if not has_multiple_updates(d):
                return f"""

    def {GeneratorUtils.method_declaration(d.update_methods[0])}:
        with self._lock:
            self.{request_state_name(d)}.response = {GeneratorUtils.response_type_for_definition(d)}({GeneratorUtils.forward_method_parameters_dict_style(GeneratorUtils.data_class_members(d, d.update_methods[0]))})
        self.dispatch_global_request_cbs(self.{request_state_name(d)})"""
            else:    
                return f"""

    def {GeneratorUtils.method_declaration(d.update_methods[0])}:
        with self._lock:
            if self.{request_state_name(d)}.response is None:
                self.{request_state_name(d)}.response = [] 
            self.{request_state_name(d)}.response.append({GeneratorUtils.type_name(d.update_methods[0].__name__)}({GeneratorUtils.forward_method_parameters_dict_style(GeneratorUtils.data_class_members(d, d.update_methods[0]))}))"""

        def global_streaming_method(d: ApiDefinition, u: Callable):
            pass

        def global_done_method(d: ApiDefinition):
                return f"""

    def {GeneratorUtils.method_declaration(d.done_method)}:
        self.dispatch_global_request_cbs(self.{request_state_name(d)})"""

        with open(filename, "w") as f:
            f.write(f"""
import asyncio
import functools
from ibapi.client import *
from ibapi.wrapper import *
from ib_wrapper.asyncio.ib_client_base import *
from ib_wrapper.gen.ib_client_responses import *
from typing import Callable, Dict, List

class IBAsyncioClient(IBClientBase):
{declare_callback_containers()}

    def __init__(self):
        IBClientBase.__init__(self)
        {initialize_callback_containers()}
"""
            )
            for d in ApiDefinitionManager.DEFINITIONS:
                if d.update_methods is None:
                    continue
                f.write(async_method(d))
                if d.req_id_names is None:
                    if len(d.update_methods) == 1:
                        f.write(global_single_update_method(d))
                        if d.done_method is not None:
                            f.write(global_done_method(d))
