from ariadne import make_executable_schema, load_schema_from_path
from ariadne.asgi import GraphQL
from ib_tws_server.gen.asyncio_client import AsyncioClient
from ib_tws_server.gen.graphql_resolver import query, subscription, graphql_resolver_set_client, union_types
import logging
import os
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send
import sys
from typing import Union

logging.basicConfig(stream=sys.stdout, level=logging.WARN)
logger = logging.getLogger()

class IbClientLifespan:
    app: ASGIApp
    receive: Receive
    send: Send
    ib_client: AsyncioClient

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "lifespan":
            await self.app(scope, receive, send)
            return
        # Implement the lifespan ASGI protocol for clean shutdowns
        # https://asgi.readthedocs.io/en/latest/specs/lifespan.html
        msg = await receive()
        if msg["type"] != "lifespan.startup":
            raise RuntimeError(f"Unexpected Lifetime event {msg}")
        print("REceived start up...")
        self.ib_client = self.create_and_start_ib_client()
        await send({"type": "lifespan.startup.complete"})
        msg = await receive()
        if msg["type"] != "lifespan.shutdown":
            raise RuntimeError(f"Unexpected Lifetime event {msg}")
        self.ib_client.disconnect(True)
        await send({"type": "lifespan.shutdown.complete"})

    # Create the client object that interacts with TWS and start the connection
    def create_and_start_ib_client(self):
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

def create_app():
    type_defs = load_schema_from_path("ib_tws_server/gen/schema.graphql")
    schema = make_executable_schema(type_defs, query, subscription, union_types)
    ariadneApp = GraphQL(schema, debug=True)
    # Wrap ariadne with CORS middleware for CORS handling
    corsWrapper = CORSMiddleware(app=ariadneApp, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
    # Wrap with IB client lifespan wrapper
    return IbClientLifespan(corsWrapper)

app = create_app()
