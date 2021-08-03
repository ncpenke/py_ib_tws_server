from ariadne import MutationType, QueryType, SubscriptionType, make_executable_schema, load_schema_from_path, convert_kwargs_to_snake_case
from ariadne.asgi import GraphQL
from ariadne.graphql import subscribe
from ariadne.objects import MutationType
import asyncio
from ib_tws_server.gen.asyncio_client import AsyncioClient
from ib_tws_server.gen.graphql_resolver import query, graphql_resolver_set_client
import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
type_defs = load_schema_from_path("ib_tws_server/gen/schema.graphql")

mutation = MutationType()
subscription = SubscriptionType()
queue = asyncio.Queue(maxsize=0)

users=dict()
messages=[]
queues = []
""" 

@query.field("hello")
def resolve_hello(*_):
    return "Hello world!"


@query.field("messages")
@convert_kwargs_to_snake_case
async def resolve_messages(obj, info, user_id):
    def filter_by_userid(message):
        return message["sender_id"] == user_id or \
               message["recipient_id"] == user_id

    user_messages = filter(filter_by_userid, messages)
    return {
        "success": True,
        "messages": user_messages
    }

@query.field("userId")
@convert_kwargs_to_snake_case
async def resolve_user_id(obj, info, username):
    user = users.get(username)
    if user:
        return user["user_id"]

@query.field("currentTime")
async def resolve_current_time(obj, info):
    return (await c.reqCurrentTime()).time

@mutation.field("createUser")
@convert_kwargs_to_snake_case
async def resolve_create_user(obj, info, username):
    try:
        if not users.get(username):
            user = {
                "user_id": len(users) + 1,
                "username": username
            }
            users[username] = user
            return {
                "success": True,
                "user": user
            }
        return {
            "success": False,
            "errors": ["Username is taken"]
        }

    except Exception as error:
        return {
            "success": False,
            "errors": [str(error)]
        }

@mutation.field("createMessage")
@convert_kwargs_to_snake_case
async def resolve_create_message(obj, info, content, sender_id, recipient_id):
    try:
        message = {
            "content": content,
            "sender_id": sender_id,
            "recipient_id": recipient_id
        }
        messages.append(message)
        for queue in queues:
            await queue.put(message)
        return {
            "success": True,
            "message": message
        }
    except Exception as error:
        return {
            "success": False,
            "errors": [str(error)]
        }

@subscription.source("messages")
@convert_kwargs_to_snake_case
async def messages_source(obj, info, user_id):
    queue = asyncio.Queue()
    queues.append(queue)
    try:
        while True:
            print('listen')
            message = await queue.get()
            queue.task_done()
            if message["recipient_id"] == user_id:
                yield message
    except asyncio.CancelledError:
        queues.remove(queue)
        raise

@subscription.field("messages")
@convert_kwargs_to_snake_case
async def messages_resolver(message, info, user_id):
    return message

@subscription.source("messages")
@convert_kwargs_to_snake_case
async def messages_source(obj, info, user_id):
    queue = asyncio.Queue()
    queues.append(queue)
    try:
        while True:
            print('listen')
            message = await queue.get()
            queue.task_done()
            if message["recipient_id"] == user_id:
                yield message
    except asyncio.CancelledError:
        queues.remove(queue)
        raise """

schema = make_executable_schema(type_defs, query)
app = GraphQL(schema, debug=True)


c = AsyncioClient()
c.start("127.0.0.1", 7496, 0)
graphql_resolver_set_client(c)
