import asyncio
from typing import Callable, Union

RequestId = Union[int, str]

class Subscription:
    def __init__(self, streaming_cb: Callable, cancel_cb: Callable, reqId: int, loop:asyncio.AbstractEventLoop):
        self.cancel_cb = cancel_cb
        self.streaming_cb = streaming_cb
        self.reqId = reqId
        self.loop = loop
    
    def cancel(self):
        if (self.reqId is None):
            self.cancel_cb()
        else:
            self.cancel_cb(self.reqId)

class RequestState():
    def __init__(self):
        self.cb = None
        self.response = None
