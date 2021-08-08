from inspect import Parameter
from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
from ib_tws_server.util.type_util import *
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
            cb_type,cb_type_is_wrapper = GeneratorUtils.callback_type(d, u)
            if not cb_type_is_wrapper:
                return ""
            ret = f"""
@dataclass(frozen=True)
class { cb_type }:
    def __init__(self, {default_params(params)}):
        {init_members(params)}"""
            ret += os.linesep.join([f"    {p}" for p in params])
            ret += os.linesep
            return ret

        with open(filename, "w") as f:
            f.write("""
from dataclasses import dataclass
from ib_tws_server.ib_imports import *
from typing import Dict, List, Union

class Error:
    reason: str
    code: int

    def __init__(self, reason: str, code: int):
        self.reason = reason
        self.code = code
""")

            for d in REQUEST_DEFINITIONS:
                if d.request_method is None or d.callback_methods is None:
                    continue
                for u in d.callback_methods:
                    f.write(callback_class(d, u))
