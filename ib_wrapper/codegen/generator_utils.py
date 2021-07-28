from os import stat
from subprocess import call
from ib_wrapper.api_definition import ApiDefinition
import inspect
from typing import Callable, List

class GeneratorUtils:
    @staticmethod
    def type_name(name: str):
        return name[0].upper() + name[1:]    
        
    @staticmethod
    def streaming_type(d: ApiDefinition):
        if d.stream_methods is None:
            return None
        return f"{GeneratorUtils.type_name(d.request_method.__name__)}Stream"

    @staticmethod
    def response_type(d: ApiDefinition):
        if d.update_methods is None:
            return 'None'
        return f"{GeneratorUtils.type_name(d.request_method.__name__)}Response"

    @staticmethod
    def data_class_members(d: ApiDefinition, methods: List[Callable], streaming_class: bool) -> List[inspect.Parameter]:
        to_skip = [ "self" ]
        if d.has_done_flag and d.update_methods is not None and not streaming_class:
            to_skip.append("done")
        if d.req_id_names is not None:
            to_skip.extend(d.req_id_names)
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