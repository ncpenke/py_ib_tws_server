from inspect import Parameter
from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
import os
from typing import List

class ResponseTypesGenerator:
    @staticmethod
    def generate(filename):
        def default_params(params: List[Parameter]):
            return ", ".join([f"{p}= None" for p in params])

        def init_members(params: List[Parameter]):
            return "        ".join([f"object.__setattr__(self, '{p.name}', {p.name}){os.linesep}" for p in params])

        def callback_class(d: ApiDefinition, u: Callable):
            params = GeneratorUtils.data_class_members(d, [u], False)
            ret = f"""
@dataclass(frozen=True)
class { GeneratorUtils.callback_type(u) }:
    def __init__(self, {default_params(params)}):
        {init_members(params)}"""
            ret += os.linesep.join([f"    {p}" for p in params])
            ret += os.linesep
            return ret

        def top_level_class(d: ApiDefinition, is_subscription: bool) -> str:
           # params = GeneratorUtils.data_class_members(d, d.callback_methods, is_subscription)
            members: List[Parameter] = [ Parameter(name=e.__name__, annotation=GeneratorUtils.callback_type(e), kind=Parameter.POSITIONAL_OR_KEYWORD) for e in d.callback_methods ]
            ret = f"""
@dataclass(frozen=True)
class { GeneratorUtils.top_level_type(d, is_subscription) }:
    def __init__(self, {default_params(members)}):
        {init_members(members)}"""
            ret += os.linesep.join([f"    {p}" for p in members])
            ret += os.linesep
            return ret

        with open(filename, "w") as f:
            f.write("""
from dataclasses import dataclass
from ib_tws_server.ib_imports import *
from typing import List
"""         )

            for d in REQUEST_DEFINITIONS:
                if d.request_method is None or d.callback_methods is None:
                    continue
                f.write(top_level_class(d, d.is_subscription))
                if d.subscription_flag_name is not None:
                    f.write(top_level_class(d, True))
                for u in d.callback_methods:
                    f.write(callback_class(d, u))
