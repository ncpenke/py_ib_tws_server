from inspect import Parameter

from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
from ib_tws_server.ib_imports import *
import logging
import os

logger = logging.getLogger()

class GraphQLSchemaGenerator:
    @staticmethod
    def generate(filename):
        ib_api_types: Set[str] = set() 
        processed_types: Set[str] = set()
        builtin_type_mappings = {
            'str': 'String',
            'bool': 'Boolean',
            'int': "Int",
            'float': 'Float'
        }
        scalars: Set[str] = set()
        enums: Set[str] = set()

        enums.add('OrderCondition')

        def add_ib_api_type(s: str):
            if s in builtin_type_mappings or s in processed_types or s in ApiDefinitionManager.TYPE_MAPPINGS:
                return
            logger.log(logging.DEBUG, f"Adding {s}")
            ib_api_types.add(s)

        def add_scalar(s: str, reason: str):
            if s in scalars:
                return
            logger.log(logging.ERROR, f"Adding scalar {s} because {reason}")
            if (s == 'str'):
                raise

            if s in builtin_type_mappings:
                raise RuntimeError(f"Should not have added {s} as scalar")
            scalars.add(s)

        def add_enum(e: str):
            if e in enums:
                return
            logger.log(logging.DEBUG, f"Adding enum {e}")
            enums.add(e)

        def graphql_type_from_type_definition(td: TypeDefinition):
            item_type = graphql_type(td.item_type)
            if item_type is None:
                raise RuntimeError(f"Unknown nested type {item_type}")
            if td.container_type is not None:
                if td.container_type == list or td.container_type == set: 
                    return f"[{item_type}]"
                else:
                    raise RuntimeError(f"Unknown container time {td.container_type}")
            else:
                return item_type

        def graphql_type(t: str):
            if t in builtin_type_mappings:
                return builtin_type_mappings[t]
            elif t in ApiDefinitionManager.TYPE_MAPPINGS:
                return graphql_type_from_type_definition(ApiDefinitionManager.TYPE_MAPPINGS[t])
            elif t in globals():
                rt = globals()[t]
                if isinstance(rt, Enum):
                    add_enum(t)
                elif (rt.__name__ != t):
                    add_scalar(t, f"Type alias")
                else:
                    add_ib_api_type(t)
                return t
            else:
                return None

        def object_member_type(obj:object, method_name: str, val: any):
            if obj.__class__.__name__ in ApiDefinitionManager.OBJECT_TYPE_ANNOTATIONS:
                d = ApiDefinitionManager.OBJECT_TYPE_ANNOTATIONS[obj.__class__.__name__]
                if method_name in d:
                    return graphql_type_from_type_definition(d[method_name])
            if val is not None:
                return graphql_type(type(val).__name__)
            else:
                raise RuntimeError(f"Could not determine type {obj.__class__.__name__} for member {method_name}")

        def generate_global_type(type_name: str):
            if type_name in processed_types or type_name in enums:
                return ""

            logger.log(logging.DEBUG, f"Generating {type_name}")

            obj = globals()[type_name]()
            processed_types.add(type_name)
            members = [ (n, object_member_type(obj, n, t)) for n,t in inspect.getmembers(obj) if not n.startswith("__")  ]
            for m,t in members:
                if t is None:
                    add_scalar(obj.__class__.__name__, f"Could not find type for member '{m}'' for class '{obj.__class__.__name__}'")
                    return ""

            code = f"""

type {obj.__class__.__name__} {{"""
            for p,t in members:
                code += f"""
    {p}: {graphql_type(t.__class__.__name__)}!"""
            code = code + """
}"""
            return code

        def generate_callback_type(d: ApiDefinition, m: Callable):
            type_name = GeneratorUtils.callback_type(m)
            if type_name in processed_types:
                return ""
            logger.log(logging.DEBUG, f"Generating {type_name}")
            params = GeneratorUtils.data_class_members(d, [m], d.is_subscription)
                
            for m in params:
                f = graphql_type(m.annotation)
                if f is None:
                    add_scalar(type_name, f"Could not find type for {m.annotation}")
                    return ""

            processed_types.add(type_name)
            code = f"""

type {type_name} {{"""
            for p in params:
                code += f"""
    {p.name}: {graphql_type(p.annotation)}!"""
                code = code + """
}"""
                return code          

        def generate_enum(e: str):
            code = f""" 
enum {e} {{"""
            for k,v in inspect.getmembers(globals()[e]):
                if isinstance(v, int):
                    code += f"""
    {k}"""
            code += """
}"""
            return code

        def generate_top_level_type(d: ApiDefinition, is_subscription: bool):
            type_name = GeneratorUtils.top_level_type(d, is_subscription)
            logger.log(logging.DEBUG, f"Generating {type_name} {is_subscription}")
            code = f"""

type {type_name} {{"""
            for m in d.callback_methods:
                code += f"""
    {m.__name__}: {GeneratorUtils.callback_type(m)}!"""
            code = code + """
}"""

            return code          

        with open(filename, "w") as f:
            for d in ApiDefinitionManager.REQUEST_DEFINITIONS:
                if d.request_method is None or d.callback_methods is None:
                    continue
                f.write(generate_top_level_type(d, d.is_subscription))
                if d.subscription_flag_name is not None:
                    f.write(generate_top_level_type(d, True))
                for m in d.callback_methods:
                    f.write(generate_callback_type(d, m))
            while len(ib_api_types) != 0:
                types = ib_api_types
                ib_api_types = set()
                for s in types:
                    f.write(generate_global_type(s))
                f.write(os.linesep)
            for e in enums:
                f.write(generate_enum(e))
                f.write(os.linesep)
            for s in scalars:
                f.write(os.linesep)
                f.write(f"scalar {s}")
            f.write(os.linesep)
