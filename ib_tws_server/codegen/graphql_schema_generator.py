from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
from ib_tws_server.ib_imports import *
from ib_tws_server.util.type_util import *
import logging
import os
import re

logger = logging.getLogger()

class GraphQLSchemaGenerator:
    @staticmethod
    def generate(filename):
        builtin_type_mappings = {
            'str': 'String',
            'bool': 'Boolean',
            'int': "Int",
            'float': 'Float'
        }

        unprocessed_types: Set[str] = set() 
        processed_types: Set[str] = set()
        scalars: Set[str] = set()
        enums: Set[str] = set()
        processing_inputs = False

        # TODO: revisit
        enums.add('OrderCondition')

        def add_type_for_processing(s: str):
            if s in builtin_type_mappings or s in processed_types:
                return
            logger.log(logging.DEBUG, f"Adding {s}")
            unprocessed_types.add(s)

        def add_scalar(s: str, reason: str, warn: bool):
            if s in scalars:
                return
            logger.log(logging.WARN if warn else logging.DEBUG, f"Adding scalar {s} because {reason}")
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

        container_re = re.compile("(?:typing\.)?(Set|List)\[([^\]]+)\]")
        def graphql_type(t: str):
            m = container_re.match(t)
            if t.startswith("ibapi."):
                # For ibapi classes strip the qualified module name since all the classes are imported directly
                return graphql_type(t.split(".")[-1])
            elif m is not None and len(m.groups()) == 2:
                container_type = m.group(1)
                return f"[{graphql_type(m.group(2))}]"
            elif t in builtin_type_mappings:
                return builtin_type_mappings[t]
            elif hasattr(OverriddenTypeAliases, t):
                overridden_type =  getattr(OverriddenTypeAliases, t)
                if str(overridden_type).find("typing.Dict") >= 0:
                    add_scalar(t, "Dict", False)
                    return t
                else:
                    return graphql_type(GeneratorUtils.type_to_type_name_str(overridden_type))
            elif hasattr(EnumAliases, t):
                return graphql_type(getattr(EnumAliases, t))
            else:
                rt = find_global_sym(t)
                if rt is not None:
                    if isinstance(rt, Enum):
                        add_enum(t)
                        return t
                    elif t in scalars or t in enums:
                        return t
                    elif (rt.__name__ != t):
                        add_scalar(t, f"Type alias", False)
                        return t
                    else:
                        add_type_for_processing(t)
                        return f"{t}Input" if processing_inputs else f"{t}"
                else:
                    raise RuntimeError(f"Could not determine type for {t}")

        def object_member_type(obj:object, member_name: str, val: any):
            if hasattr(OverriddenMemberTypeHints, obj.__class__.__name__):
                hints = getattr(OverriddenMemberTypeHints, obj.__class__.__name__)
                if hasattr(hints,member_name):
                    return graphql_type(GeneratorUtils.type_to_type_name_str(getattr(hints, member_name)))
            if val is not None:
                return graphql_type(type(val).__name__)
            else:
                raise RuntimeError(f"Could not determine type {obj.__class__.__name__} for member {member_name}")

        def generate_global_type(type_name: str):
            if type_name in processed_types or type_name in enums:
                return ""

            logger.log(logging.DEBUG, f"Generating {type_name}")

            cls = globals()[type_name]
            cls_dict = cls.__dict__
            processed_types.add(type_name)
            if ('__annotations__' in cls_dict):
                members = [ (k,v) for k,v in cls_dict['__annotations__']  ]
            else:
                obj = cls()
                members = [ (n, object_member_type(obj, n, t)) for n,t in inspect.getmembers(obj) if not n.startswith("__")  ]
            for m,t in members:
                if t is None:
                    add_scalar(cls.__name__, f"Could not find type for member '{m}'' for class '{cls.__name__}'", True)
                    return ""

            code = f"""

{'input' if processing_inputs else 'type'} {obj.__class__.__name__}{'Input' if processing_inputs else ''} {{"""
            for p,t in members:
                code += f"""
    {p}: {t}"""
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
                    add_scalar(type_name, f"Could not find type for {m.annotation}", True)
                    return ""

            processed_types.add(type_name)
            code = f"""

type {type_name} {{"""
            for p in params:
                code += f"""
    {p.name}: {graphql_type(p.annotation)}"""
            code += """
}"""
            return code          

        def generate_enum(e: str):
            code = f""" 
enum {e} {{"""
            for k,v in inspect.getmembers(globals()[e]):
                if isinstance(v, int):
                    code += f"""
    {k.replace("/", "")}"""
            code += """
}"""
            return code

        def generate_top_level_type(d: ApiDefinition, is_subscription: bool):
            type_name = GeneratorUtils.top_level_type(d, is_subscription)
            if type_name in processed_types:
                raise RuntimeError(f"Top level type {type_name} already processed")
            processed_types.add(type_name)
            logger.log(logging.DEBUG, f"Generating {type_name} {is_subscription}")
            code = f"""

type {type_name} {{"""
            for m in d.callback_methods:
                code += f"""
    {m.__name__}: {GeneratorUtils.callback_type(m)}"""
            code = code + """
}"""
            return code   

        def graphql_request_return_type(t: str):
            m = container_re.match(t)
            if m is not None and len(m.groups()) == 2:
                if m.group(1) == "List":
                    return f"[{m.group(2)}]"
                else:
                    raise RuntimeError(f"Unexpected container type {t}")
            else:
                return t

        def generate_query_or_subscription(d: ApiDefinition, is_subscription: bool):
            name = GeneratorUtils.request_method_name(d, d.request_method, is_subscription)
            members = GeneratorUtils.data_class_members(d, [d.request_method], False)
            annotations = []
            for m in members:
                gql = graphql_type(m.annotation)
                annotations.append(gql)
            members = [ f"{m.name}: {a}" for (m,a) in zip(members,annotations) ]
            member_str = ",".join(members)
            member_sig =  "" if len(member_str) == 0 else f"({member_str})"
            return f"""
    {name}{member_sig}: {graphql_request_return_type(GeneratorUtils.request_return_type(d, is_subscription))}"""

        with open(filename, "w") as f:
            for d in REQUEST_DEFINITIONS:
                if d.request_method is None or d.callback_methods is None:
                    continue
                f.write(generate_top_level_type(d, d.is_subscription))
                if d.subscription_flag_name is not None:
                    f.write(generate_top_level_type(d, True))
                for m in d.callback_methods:
                    f.write(generate_callback_type(d, m))
            while len(unprocessed_types) != 0:
                s = unprocessed_types.pop()
                ret = generate_global_type(s)
                if len(ret) > 0:
                    f.write(ret)
                    f.write(os.linesep)
            processed_types = set()
            processing_inputs = True
            f.write("""
type Query {""")
            for d in REQUEST_DEFINITIONS:
                if d.request_method is not None and not d.is_subscription and d.callback_methods is not None:
                    f.write(generate_query_or_subscription(d, False))
            f.write("""
}
type Subscription {""")
            for d in REQUEST_DEFINITIONS:
                if d.request_method is not None and (d.is_subscription or d.subscription_flag_name is not None) and d.callback_methods is not None:
                    f.write(generate_query_or_subscription(d, True))
            f.write("""
}""")
            f.write(os.linesep)
            while len(unprocessed_types) != 0:
                s = unprocessed_types.pop()
                ret = generate_global_type(s)
                if len(ret) > 0:
                    f.write(ret)
                    f.write(os.linesep)
            for e in enums:
                f.write(generate_enum(e))
                f.write(os.linesep)
            for s in scalars:
                f.write(os.linesep)
                f.write(f"scalar {s}")
            f.write(os.linesep)
            f.write("""
schema {
    query: Query
    subscription: Subscription
}
""")