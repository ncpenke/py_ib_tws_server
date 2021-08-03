from ib_tws_server.util.dict_to_object import dict_to_object
from ib_tws_server.util.type_util import *
from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
from ib_tws_server.ib_imports import *
import logging

logger = logging.getLogger()

class GraphQLResolverGenerator:
    @staticmethod
    def generate(filename):
        def transform_to_object_if_dict(type_str: str, value_str: str):
            if is_builtin_type_str(type_str):
                return value_str
            cls = find_global_sym(type_str)
            if cls is None:
                raise RuntimeError(f"Could not find symbol for {type_str}")
            return f"dict_to_object({value_str}, {type_str})"

        def query_resolver(d: ApiDefinition):
            query_name = d.request_method.__name__
            params = GeneratorUtils.data_class_members(d, [d.request_method], False)
            query_resolver_params = [ f"{p.name}: {p.annotation}" for p in params ]
            query_resolver_params.insert(0, 'obj')
            query_resolver_params.insert(1, 'info')
            forwarded_params = [transform_to_object_if_dict(p.annotation, p.name) for p in params]

            return f"""
@query.field("{query_name}")
async def resolve_{query_name}({','.join(query_resolver_params)}):
        return await g_client.{query_name}({','.join(forwarded_params)})
            """

        with open(filename, "w") as f:
            f.write("""
from ariadne import QueryType
from ib_tws_server.util.dict_to_object import *
from ib_tws_server.gen.asyncio_client import AsyncioClient
from ib_tws_server.ib_imports import *

g_client: AsyncioClient = None
query = QueryType()

def graphql_resolver_set_client(client: AsyncioClient):
    global g_client
    g_client = client
""")
            for d in REQUEST_DEFINITIONS:
                if d.request_method is not None and d.callback_methods is not None:
                    if not d.is_subscription:
                        f.write(query_resolver(d))

    