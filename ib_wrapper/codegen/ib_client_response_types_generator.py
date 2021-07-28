from inspect import Parameter
from ib_wrapper.api_definition import *
from ib_wrapper.codegen.generator_utils import *
import os
from typing import List

class IBClientResponseTypesGenerator:
    @staticmethod
    def generate(filename):
        def response_classes(d: ApiDefinition):
            lines = []
            if d.update_methods is not None:
                lines.extend(data_class(d, d.update_methods, False))
            if d.stream_methods is not None:
                lines.extend(data_class(d, d.stream_methods, True))
            return lines

        def init_params(params: List[Parameter]):
            return ", ".join([f"{p}= None" for p in params])

        def init_body(params: List[Parameter]):
            return "        ".join([f"object.__setattr__(self, '{p.name}', {p.name}){os.linesep}" for p in params])

        def data_class(d: ApiDefinition, methods: List[Callable], streaming_class: bool) -> List[str]:
            params = GeneratorUtils.data_class_members(d, methods, streaming_class)
            lines = [f"""
@dataclass(frozen=True)
class {GeneratorUtils.streaming_type(d) if streaming_class else GeneratorUtils.response_type(d)}:
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
