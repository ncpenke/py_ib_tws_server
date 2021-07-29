from os import stat
from subprocess import call
from ib_tws_server.api_definition import ApiDefinition
import inspect
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
        return f"{GeneratorUtils.type_name(d.request_method.__name__)}Stream"

    @staticmethod
    def req_id_param_name(u: Callable):
        return list(inspect.signature(u).parameters.values())[1].name

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
            for v in inspect.signature(m).parameters.values():
                if v.name not in to_skip:
                    if v.name in processed:
                        if processed[v.name] != v.kind:
                            raise RuntimeError(f"{v.name} parameter has different types in different callbacks")
                    else:
                        processed[v.name] = v.kind
                        ret.append(v)
        return ret

    @staticmethod
    def forward_parameters(m: callable) -> str:
        params = [ v.name for v in inspect.signature(m).parameters.values() ]
        return ','.join(params)

    @staticmethod
    def method_declaration(m: callable) -> str:
        return f"{m.__name__}{str(inspect.signature(m))}"

    @staticmethod
    def modified_signature_str(c: callable, to_skip=List[str]):
        #for n,t in inspect.signature(c).parametersreplace():
        #   if not n in to_skip:
        #        ret = ret + 
        pass
