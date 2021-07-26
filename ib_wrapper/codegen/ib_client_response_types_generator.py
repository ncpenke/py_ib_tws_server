from ib_wrapper.api_definition import *
from ib_wrapper.codegen.generator_utils import *
import os
from typing import List

class IBClientResponseTypeGenerator:
    @staticmethod
    def generate(filename):
        def data_classes_for_request_definition(d: ApiDefinition):
            lines = []
            if d.update_methods is not None:
                for m in d.update_methods:
                    lines.extend(data_class_for_method(d, m))
            if d.stream_methods is not None:
                for m in d.stream_methods:
                    lines.extend(data_class_for_method(d, m))
            return lines

        def data_class_for_method(d: ApiDefinition, m: Callable) -> List[str]:
            params = GeneratorUtils.data_class_members(d, m)
            lines = [
    f"""
@dataclass(frozen=True)
class {GeneratorUtils.type_name(m.__name__)}:"""
            ]
            lines.extend([f"    {p}" for p in params])
            lines.append("")
            return lines

        def multi_update_data_class(d: ApiDefinition):
            lines = [
    f"""
@dataclass(frozen=True)
class {GeneratorUtils.response_type_for_definition(d)}:"""
            ]
            for u in d.update_methods:
                lines.append(f"    {u.__name__}: {GeneratorUtils.response_type_for_update_method(d,u)}")
            lines.append("")
            return lines

        multi_update_definitions = []

        with open(filename, "w") as f:
            f.write("""
from dataclasses import dataclass
from ibapi.wrapper import *
import ibapi.common
from typing import List
"""         )

            for d in ApiDefinitionManager.DEFINITIONS:
                f.write(os.linesep.join(data_classes_for_request_definition(d)))
                if (d.update_methods is not None and len(d.update_methods) > 1):
                    multi_update_definitions.append(d)
            for d in multi_update_definitions:
                f.write(os.linesep.join(multi_update_data_class(d)))
