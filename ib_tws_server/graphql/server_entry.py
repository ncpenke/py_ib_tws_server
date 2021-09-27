from ariadne import MutationType, QueryType, SubscriptionType, make_executable_schema, load_schema_from_path, convert_kwargs_to_snake_case
from ariadne.asgi import GraphQL
from ariadne.graphql import subscribe
from ariadne.objects import MutationType
import asyncio
from ib_tws_server.gen.asyncio_client import AsyncioClient
from ib_tws_server.gen.graphql_resolver import query, subscription, graphql_resolver_set_client, union_types
import logging
import os
from starlette.middleware.cors import CORSMiddleware
import sys

logging.basicConfig(stream=sys.stdout, level=logging.WARN)
logger = logging.getLogger()

def create_app():
    type_defs = load_schema_from_path("ib_tws_server/gen/schema.graphql")
    mutation = MutationType()
    queue = asyncio.Queue(maxsize=0)

    users=dict()
    messages=[]
    queues = []

    schema = make_executable_schema(type_defs, query, subscription, union_types)
    return CORSMiddleware(app=GraphQL(schema, debug=True), allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

def create_ib_client():
    c = AsyncioClient()
    host = os.getenv('IB_SERVER_HOST')
    port = os.getenv('IB_SERVER_PORT')

    if host is None:
        logger.warn(f"IB_SERVER_HOST is not set. Using default")
        host = "127.0.0.1"
    if port is None:
        logger.warn(f"IB_SERVER_PORT is not set. Using default")
        port = 7496
    else:
        port = int(port)

    connection_retry_interval = 5
    c.start(host, port, 0, connection_retry_interval)
    graphql_resolver_set_client(c)
    return c

app = create_app()
ib_client = create_ib_client()

