from ariadne import MutationType, QueryType, SubscriptionType, make_executable_schema, load_schema_from_path, convert_kwargs_to_snake_case
from ariadne.asgi import GraphQL
from ariadne.graphql import subscribe
from ariadne.objects import MutationType
import asyncio
from ib_tws_server.gen.asyncio_client import AsyncioClient
from ib_tws_server.gen.graphql_resolver import query, subscription, graphql_resolver_set_client, union_types
import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
type_defs = load_schema_from_path("ib_tws_server/gen/schema.graphql")

mutation = MutationType()
queue = asyncio.Queue(maxsize=0)

users=dict()
messages=[]
queues = []

schema = make_executable_schema(type_defs, query, subscription, union_types)
app = GraphQL(schema, debug=True)

c = AsyncioClient()
c.start("127.0.0.1", 7496, 0)
graphql_resolver_set_client(c)
