from typing import Generator
from ib_tws_server.util.dict_to_object import dict_to_object
from ib_tws_server.util.type_util import *
from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
from ib_tws_server.ib_imports import *
import logging
import re

logger = logging.getLogger()

class GraphQLResolverGenerator:
    @staticmethod
    def generate(filename):
        container_re = re.compile("(?:typing\.)?List\[([^\]]+)\]")
        union_types = []

        def transform_param_if_needed(type_str: str, value_str: str):
            if is_builtin_type_str(type_str):
                return ""
            
            m = container_re.match(type_str)
            if (m is not None):
                item_type_str = m.group(1)
                return f"""
    {value_str} = [  dict_to_object(val, {item_type_str}) for val in {value_str} ]"""

            cls = find_sym_from_full_name_or_module(type_str, ibapi)
            if cls is None:
                raise RuntimeError(f"Could not find symbol for {type_str}")
            return f"""
    {value_str} = dict_to_object({value_str}, {type_str})"""

        def query_resolver(d: ApiDefinition):
            query_name = d.request_method.__name__
            params = GeneratorUtils.graphql_request_params(d, False)
            query_resolver_params = [ f"{p.name}: {p.annotation}" for p in params ]
            query_resolver_params.insert(0, 'obj')
            query_resolver_params.insert(1, 'info')
            forwarded_params = [ p.name for p in params ]
            transformed_params = "".join([transform_param_if_needed(p.annotation, p.name) for p in params])

            return f"""
@query.field("{query_name}")
async def resolve_{query_name}({','.join(query_resolver_params)}):
    {transformed_params}
    return await g_client.{query_name}({','.join(forwarded_params)})"""

        def subscription_source_and_resolver(d: ApiDefinition):
            sub_name = d.request_method.__name__
            api_sub_name = GeneratorUtils.request_method_name(d, True)
            params = GeneratorUtils.graphql_request_params(d, True)
            decl_params = [ f"{p.name}: {p.annotation}" for p in params ]
            decl_params.insert(0, 'obj')
            decl_params.insert(1, 'info')
            decl_params_str = ','.join(decl_params)
            forwarded_params = [ p.name for p in params ]
            transformed_params = "".join([transform_param_if_needed(p.annotation, p.name) for p in params])

            return f"""
@subscription.source("{sub_name}")
async def source_{sub_name}({decl_params_str}) -> AsyncGenerator:
    {transformed_params}
    return await g_client.{api_sub_name}({','.join(forwarded_params)})

@subscription.field("{sub_name}")
async def resolve_{sub_name}({decl_params_str}):
    return obj
"""

        def union_type_resolver(d: ApiDefinition):
            if not GeneratorUtils.query_return_item_type_is_union(d):
                return ""

            union_type = GeneratorUtils.query_return_item_type(d)
            ret = f"""
union_{union_type} = UnionType("{union_type}")
@union_{union_type}.type_resolver
def resolve_{union_type}(obj, *_):"""
            first = True
            for c in d.callback_methods:
                callback_type,wrapper_type = GeneratorUtils.callback_type(d, c)
                ret += f"""
    {"if" if first else "elif"} isinstance(obj, {callback_type}):
        return "{callback_type}"
"""
                first = False
            ret += f"""
    return None
"""
            union_types.append(f"union_{union_type}")
            return ret

        with open(filename, "w") as f:
            f.write("""
from ariadne import QueryType, SubscriptionType, UnionType
from ib_tws_server.util.dict_to_object import *
from ib_tws_server.gen.asyncio_client import AsyncioClient
from ib_tws_server.gen.client_responses import *
from ib_tws_server.ib_imports import *
from typing import AsyncGenerator

g_client: AsyncioClient = None
query = QueryType()
subscription = SubscriptionType()

def graphql_resolver_set_client(client: AsyncioClient):
    global g_client
    g_client = client
""")
            for d in REQUEST_DEFINITIONS:
                if d.request_method is not None and d.callback_methods is not None:
                    if not d.is_subscription:
                        f.write(query_resolver(d))
                        if d.subscription_flag_name is not None:
                           f.write(subscription_source_and_resolver(d))
                    else:
                        f.write(subscription_source_and_resolver(d))
                    f.write(union_type_resolver(d))
            f.write(f"union_types = [{','.join(union_types)}]")

    