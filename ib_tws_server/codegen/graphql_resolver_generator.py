from ib_tws_server.api_definition import *
from ib_tws_server.codegen.generator_utils import *
from ib_tws_server.ib_imports import *
from inspect import Parameter, Signature
import logging

logger = logging.getLogger()

class GraphQLResolverGenerator:
    @staticmethod
    def generate(filename):
        def query_resolver(d: ApiDefinition):
            method_name = GeneratorUtils.request_method_name(d, d.request_method, False)
            query_name = d.request_method.__name__
            params = GeneratorUtils.data_class_members(d, [d.request_method], False)
            query_resolver_params = params.copy()
            query_resolver_params.insert(0, Parameter('obj', Parameter.POSITIONAL_OR_KEYWORD))
            query_resolver_params.insert(1, Parameter('info', Parameter.POSITIONAL_OR_KEYWORD))
            signature = Signature(query_resolver_params)

            return f"""
@query.field("{query_name}")
async def resolve_{query_name}{signature}:
        return await g_client.{query_name}({','.join([p.name for p in params])})
            """

        with open(filename, "w") as f:
            f.write("""
from ariadne import QueryType
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

    