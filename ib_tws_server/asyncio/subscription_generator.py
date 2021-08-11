import asyncio
from asyncio.queues import Queue
from ib_tws_server.asyncio.request_state import RequestId
from typing import AsyncGenerator, Awaitable, Callable, TypeVar, Union

YieldType = TypeVar("YieldType")

class SubscriptionGenerator(AsyncGenerator[YieldType, None]):
    CancelCbType = Union[Callable[[RequestId],None],Callable[[],None]]
    _req_id: RequestId
    _cancel_cb: CancelCbType
    _queue: asyncio.Queue[YieldType]

    def __init__(self, cancel_cb: CancelCbType, reqId: RequestId):
        self._cancel_cb = cancel_cb
        self._req_id = reqId
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()

    def add_to_queue(self, val: YieldType):
        self._queue.put_nowait(val)
        super().asend

    async def __anext__(self) -> YieldType:
        return await self._queue.get()
        
    def __aiter__(self):
        return self
     
    async def aclose(self) -> Awaitable[None]:
        if (self._req_id is None):
            self._cancel_cb()
        else:
            self._cancel_cb(self._req_id)

    async def asend(self, value: YieldType) -> Awaitable[YieldType]:
        pass 

    async def athrow(self, type: BaseException) -> Awaitable[YieldType]:
        raise type
