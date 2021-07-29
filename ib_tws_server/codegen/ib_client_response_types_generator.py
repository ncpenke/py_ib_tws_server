from inspect import Parameter
from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
import os
from typing import List

class IBClientResponseTypesGenerator:
    @staticmethod
    def generate(filename):
        def response_classes(d: ApiDefinition):
            lines = []
            if d.callback_methods is not None:
                lines.extend(data_class(d, d.is_subscription))
                if d.subscription_flag_name is not None:
                    lines.extend(data_class(d, True))
            return lines

        def init_params(params: List[Parameter]):
            return ", ".join([f"{p}= None" for p in params])

        def init_body(params: List[Parameter]):
            return "        ".join([f"object.__setattr__(self, '{p.name}', {p.name}){os.linesep}" for p in params])

        def data_class(d: ApiDefinition, is_subscription: bool) -> List[str]:
            params = GeneratorUtils.data_class_members(d, d.callback_methods, is_subscription)
            lines = [f"""
@dataclass(frozen=True)
class { GeneratorUtils.streaming_type(d) if is_subscription else GeneratorUtils.response_type(d) }:
    def __init__(self, {init_params(params)}):
        {init_body(params)}"""]
            lines.extend([f"    {p}" for p in params])
            lines.append("")
            return lines

        with open(filename, "w") as f:
            f.write("""
from dataclasses import dataclass
import ibapi.common
import ibapi.contract
import ibapi.execution
import ibapi.order
import ibapi.order_state
import ibapi.scanner
from typing import List
"""         )

            for d in ApiDefinitionManager.DEFINITIONS:
                if d.request_method is None:
                    continue
                f.write(os.linesep.join(response_classes(d)))
