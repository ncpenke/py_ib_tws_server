from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
from ib_tws_server.ib_imports import *
from ib_tws_server.util.type_util import *
from inspect import *
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

        callback_types: Set[str] = set()
        unprocessed_types: Set[(str,bool)] = set() 
        processed_types: Dict[str, str] = {}
        scalars: Set[str] = set()
        enums: Set[str] = set()
        union_types: Set[str] = set()
        container_re = re.compile("(?:typing\.)?(Set|List)\[([^\]]+)\]")
        dict_re = re.compile("(?:typing\.)?Dict\[[\s]*([a-zA-Z\.]+)[\s]*,[\s]*([a-zA-Z\.]+)\]")

        # TODO: revisit
        enums.add('ibapi.order_condition.OrderCondition')

        def graphql_type_name(s:str, is_input: bool):
            return f"{GeneratorUtils.unqualified_type_name(s)}{'Input' if is_input else ''}"

        def check_if_processed(s:str, is_input: bool):
            u = graphql_type_name(s, is_input)
            if u in processed_types:
                if processed_types[u] != s:
                    if (not s.startswith('ibapi')) or (not processed_types[u].startswith('ibapi')):
                        raise RuntimeError(f"Duplicate unqualified type {processed_types[u]} != {s}")
                return True
            return False

        def add_type_for_processing(s: str, is_input: bool):
            if s in builtin_type_mappings or s in callback_types or s in union_types or check_if_processed(s, is_input) or (s,is_input) in unprocessed_types:
                return
            m = container_re.match(s)
            if m is not None:
                type_to_add = m.group(2)
            else:
                type_to_add = s
            logger.log(logging.DEBUG, f"Adding {type_to_add}")
            unprocessed_types.add((type_to_add, is_input))

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

        def graphql_type(t: str, is_input: bool):
            m = container_re.match(t)

            if m is not None and len(m.groups()) == 2:
                return f"[{graphql_type(m.group(2), is_input)}]"
            elif t in builtin_type_mappings:
                return builtin_type_mappings[t]
            elif t in callback_types or t in union_types:
                return t
            elif t in ENUM_ALIASES:
                return graphql_type(ENUM_ALIASES[t], is_input)
            else:
                dict_m = dict_re.match(t)
                if dict_m is not None:
                    type_name = f"{GeneratorUtils.unqualified_type_name(dict_m.group(2))}Map"
                    add_scalar(type_name, "Dictionary", False)
                    return type_name
                resolved_type = find_sym_from_full_name_or_module(t, ibapi)
                ret_type_str =  GeneratorUtils.unqualified_type_name(t)
                if resolved_type is not None:
                    if isinstance(resolved_type, ibapi.common.Enum):
                        add_enum(t)
                        return ret_type_str
                    elif t in scalars or t in enums:
                        return ret_type_str
                    else:
                        add_type_for_processing(t, is_input)
                        return graphql_type_name(t, is_input)
                else:
                    raise RuntimeError(f"Could not determine type for {t}")

        def object_member_type(obj:object, member_name: str, val: any, is_input: bool):
            if obj.__class__.__name__ in OVERRIDDEN_MEMBER_TYPE_HINTS :
                hints = OVERRIDDEN_MEMBER_TYPE_HINTS[obj.__class__.__name__]
                if member_name in hints:
                    return graphql_type(hints[member_name], is_input)
            if val is not None:
                return graphql_type(full_class_name(type(val)), is_input)
            else:
                raise RuntimeError(f"Could not determine type {obj.__class__.__name__} for member {member_name}")

        def generate_global_type(type_name: str, is_input: bool):
            if check_if_processed(type_name, is_input) or type_name in enums:
                return ""

            logger.log(logging.DEBUG, f"Generating {type_name}")

            unqualified_name = graphql_type_name(type_name, is_input)
            cls =  find_sym_from_full_name_or_module(type_name, ibapi)
            if cls is None:
                raise RuntimeError(f"Could not find symbol for {type_name}")
            cls_dict = cls.__dict__
            processed_types[unqualified_name] = type_name
            if ('__annotations__' in cls_dict):
                members = [ (k,graphql_type(v)) for k,v in cls_dict['__annotations__']  ]
            else:
                obj = cls()
                members = [ (n, object_member_type(obj, n, t, is_input)) for n,t in inspect.getmembers(obj) if not n.startswith("__")  ]
            for m,t in members:
                if t is None:
                    add_scalar(cls.__name__, f"Could not find type for member '{m}'' for class '{cls.__name__}'", True)
                    return ""

            code = f"""

{'input' if is_input else 'type'} {unqualified_name} {{"""
            for p,t in members:
                code += f"""
    {p}: {t}"""
            code = code + """
}"""
            return code

        def generate_callback_type(d: ApiDefinition, m: Callable):
            type_name,is_wrapper = GeneratorUtils.callback_type(d, m)

            if not is_wrapper:
                return ""

            if type_name in processed_types:
                return ""

            callback_types.add(type_name)

            logger.log(logging.DEBUG, f"Generating {type_name}")
            params = GeneratorUtils.data_class_members(d, [m], d.is_subscription)

            for m in params:
                f = graphql_type(m.annotation, False)
                if f is None:
                    add_scalar(type_name, f"Could not find type for {m.annotation}", True)
                    return ""

            processed_types[type_name] = type_name
            code = f"""

type {type_name} {{"""
            for p in params:
                code += f"""
    {p.name}: {graphql_type(p.annotation, False)}"""
            code += """
}"""
            return code          

        def generate_enum(e: str):
            resolved_type = find_sym_from_full_name(e)
            short_name = GeneratorUtils.unqualified_type_name(resolved_type.__name__)
            code = f""" 
enum {short_name} {{"""
            for k,v in inspect.getmembers(resolved_type):
                if isinstance(v, int):
                    code += f"""
    {k.replace("/", "")}"""
            code += """
}"""
            return code

        def query_return_item_type(d: ApiDefinition):
            callback_types = GeneratorUtils.callback_types(d)
            if len(callback_types) < 2:
                return callback_types[0]
            else:
                return f"{GeneratorUtils.type_name(d.request_method.__name__)}Response"

        def generate_union_type(d: ApiDefinition):
            callback_types = GeneratorUtils.callback_types(d)
            if len(callback_types) < 2:
                return ""
            else:
                union_type = query_return_item_type(d)
                union_types.add(union_type)
                if union_type in processed_types:
                    raise RuntimeError(f"Union type {union_type} already processed")
                processed_types[union_type] = union_type
                return  f"""
union {union_type} = {"|".join([graphql_type(c, False) for c in callback_types])}
"""

        def generate_query_or_subscription(d: ApiDefinition, is_subscription: bool):
            name = d.request_method.__name__
            members = list(GeneratorUtils.request_signature(d, False).parameters.values())
            del members[0] # remove 'self'
            annotations = []
            for m in members:
                gql = graphql_type(m.annotation, True)
                annotations.append(gql)
            members = [ f"{m.name}: {a}" for (m,a) in zip(members,annotations) ]
            member_str = ",".join(members)
            member_sig =  "" if len(member_str) == 0 else f"({member_str})"
            query_return_type = graphql_type(query_return_item_type(d), False)
            if GeneratorUtils.response_is_list(d) and not is_subscription:
                query_return_type = f"[{query_return_type}]"
            return f"""
    {name}{member_sig}: {query_return_type}"""

        with open(filename, "w") as f:
            for d in REQUEST_DEFINITIONS:
                if d.request_method is None or d.callback_methods is None:
                    continue
                for c in d.callback_methods:
                    f.write(generate_callback_type(d, c))
                f.write(generate_union_type(d))

            while len(unprocessed_types) != 0:
                s,is_input = unprocessed_types.pop()
                ret = generate_global_type(s, is_input)
                if len(ret) > 0:
                    f.write(ret)
                    f.write(os.linesep)
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
                s,is_input = unprocessed_types.pop()
                ret = generate_global_type(s, is_input)
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