from subprocess import call
from ib_wrapper.api_definition import ApiDefinition
import inspect
from typing import Callable, List

class GeneratorUtils:
    @staticmethod
    def type_name(name: str):
        return name[0].upper() + name[1:]

    @staticmethod
    def response_type_for_update_method(d: ApiDefinition, u: callable):
        type = GeneratorUtils.type_name(u.__name__)
        if d.has_done_flag or d.done_method is not None:
            type = f"List[{type}]"
        return type

    @staticmethod
    def response_type_for_stream_method(d: ApiDefinition, u: callable):
        return GeneratorUtils.type_name(u.__name__)

    @staticmethod
    def response_type_for_definition(d: ApiDefinition):
        if (d.update_methods is None):
            return None
        elif (len(d.update_methods) == 1):
            return GeneratorUtils.response_type_for_update_method(d, d.update_methods[0])
        else:
            return f"{GeneratorUtils.type_name(d.request_method.__name__)}Response"

    @staticmethod
    def data_class_members(d: ApiDefinition, m: Callable) -> List[inspect.Parameter]:
        to_skip = [ "self" ]
        if d.has_done_flag and d.update_methods is not None and m in d.update_methods:
            to_skip.append("done")
        return [ v for v in inspect.signature(m).parameters.values() if v.name not in to_skip ]

    @staticmethod
    def forward_method_parameters_dict_style(params: List[inspect.Parameter]) -> str:
        return ",".join([ f"{v.name} = {v.name}" for v in params ])

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