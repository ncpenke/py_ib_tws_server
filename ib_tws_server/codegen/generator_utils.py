from os import stat
from subprocess import call
from ib_tws_server.api_definition import ApiDefinition, ApiDefinitionManager
import inspect
import re
from typing import Callable, List

class GeneratorUtils:
    @staticmethod
    def type_name(name: str):
        return name[0].upper() + name[1:]    
    
    @staticmethod
    def response_type(d: ApiDefinition):
        return f"{GeneratorUtils.type_name(d.request_method.__name__)}Response"

    @staticmethod
    def streaming_type(d: ApiDefinition):
        return f"{GeneratorUtils.type_name(d.request_method.__name__)}Update"

    @staticmethod
    def top_level_type(d: ApiDefinition, is_subscription: bool):
        return GeneratorUtils.streaming_type(d) if is_subscription else GeneratorUtils.response_type(d)

    @staticmethod
    def callback_type(u: Callable):
        return GeneratorUtils.type_name(u.__name__)

    @staticmethod
    def req_id_param_name(u: Callable):
        return list(GeneratorUtils.signature(u).parameters.values())[1].name

    @staticmethod
    def req_id_names(d: ApiDefinition):
        ret = []
        if not d.uses_req_id:
            return ret
        ret.append(GeneratorUtils.req_id_param_name(d.request_method))
        if d.callback_methods is not None:
            for m in d.callback_methods:
                ret.append(GeneratorUtils.req_id_param_name(m))
        return ret

    params_regex = re.compile("[\s]*def[\s]+[^(]+\(([^)]+)\)")
    _cached_signatures = {}
    @staticmethod
    def signature(u: object):
        if u in GeneratorUtils._cached_signatures:
            return GeneratorUtils._cached_signatures[u]
        sig = inspect.signature(u)
        if u.__name__ in ApiDefinitionManager.OVERRIDDEN_FUNCTION_SIGNATURES:
            code = ApiDefinitionManager.OVERRIDDEN_FUNCTION_SIGNATURES[u.__name__]
        else:
            code = inspect.getsource(u)
        params_raw = GeneratorUtils.params_regex.match(code).groups()[0].split(',')
        sig_params = list(sig.parameters.values())
        i = 0
        if len(sig_params) != len(params_raw):
            raise RuntimeError(f"Error in parameter parsing for method {sig}")
        for sp,raw in zip(sig_params, params_raw):
            raw = [ r.strip() for r in raw.split(":") ]
            if (raw[0] != sp.name):
                raise RuntimeError(f"Error in parameter parsing for method {sig} {raw[0]} {sp.name}")
            if (len(raw) > 1):
                sig_params[i] = sp.replace(annotation=raw[1])
            i += 1
        sig = sig.replace(parameters=sig_params)
        GeneratorUtils._cached_signatures[u] = sig
        return sig

    @staticmethod
    def data_class_members(d: ApiDefinition, methods: List[Callable], streaming_class: bool) -> List[inspect.Parameter]:
        to_skip = [ "self" ]
        if d.has_done_flag and d.callback_methods is not None and not streaming_class:
            to_skip.append("done")
        req_id_names = GeneratorUtils.req_id_names(d)
        if req_id_names is not None:
            to_skip.extend(req_id_names)
        ret = []
        processed = {}
        for m in methods:
            for v in GeneratorUtils.signature(m).parameters.values():
                if v.name not in to_skip:
                    if v.name in processed:
                        if processed[v.name] != v.annotation:
                            raise RuntimeError(f"{v.name} parameter in method {m.__name__} has different types in different callbacks {processed[v.name]} {v.annotation}")
                    else:
                        processed[v.name] = v.annotation
                        ret.append(v)
        return ret

    @staticmethod
    def forward_parameters(m: callable) -> str:
        params = [ v.name for v in GeneratorUtils.signature(m).parameters.values() ]
        return ','.join(params)

    @staticmethod
    def method_declaration(m: callable) -> str:
        return f"{m.__name__}{str(GeneratorUtils.signature(m))}"

    @staticmethod
    def doc_string(m: callable) -> str:
        return f'"""{m.__doc__}"""'