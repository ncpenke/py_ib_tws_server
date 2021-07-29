import asyncio
from collections import defaultdict
from logging import getLogger
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ib_tws_server.asyncio.ib_writer import IBWriter
from threading import Lock, Thread
from typing import Awaitable, Callable, Dict, Generic, Union, TypeVar

logger = getLogger()

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

class IBClientBase(EClient,EWrapper):
    _lock: Lock
    _req_state: Dict[str, RequestState]
    _subscriptions: Dict[int, Subscription]

    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self._writer = IBWriter(self)
        self._lock = Lock()
        self._current_request_id = 0
        self._req_state = defaultdict(RequestState)
        self._subscriptions = defaultdict(Subscription)

    def run(self):
        self._writer.start()
        EClient.run(self)

    def next_request_id(self):
        with self._lock:
            self._current_request_id += 1
            return self._current_request_id

    def connectionClosed(self):
        self._writer.queue.put(lambda *a, **k: None)

    def call_response_cb(self, id: RequestId, res=None):
        cb = None
        with self._lock:
            if not id in self._req_state:
                return

            s = self._req_state[id]
            cb = s.cb
            if res is None:
                res = s.response
            del self._req_state[id]

        if cb is not None:
            cb(res)

    def call_streaming_cb(self, id: RequestId, res: any):
        cb = None
        loop = None
        with self._lock:
            if id in self._subscriptions:
                s = self._subscriptions[id]
                cb = s.streaming_cb
                loop = s.loop
        if loop is not None:
            loop.call_soon_threadsafe(cb, res)

    def cancel_request(self, id: RequestId):
        response_cb = None
        with self._lock:
            if id in self._req_state:
                response_cb = self._req_state[id].cb
                del self._req_state[id]
            if id in self._subscriptions:
                del self._subscriptions[id]
        if response_cb is not None:
            response_cb(None)

    def start(self, host: str, port: int, client_id: int):
        self.connect(host, port, client_id)
        thread = Thread(target = self.run)
        thread.start()
        setattr(thread, "_thread", thread)

    def error(self, reqId:int, errorCode:int, errorString:str):
        logger.error(f"Response error {reqId} {errorCode} {errorString}")
        cb:Callable = None
        with self._lock:
            if reqId in self._req_state:
                cb = self._req_state[reqId].cb
                del self._req_state[reqId]
            if reqId in self._subscriptions:
                del self._subscriptions[reqId]
        if cb is not None:
            cb(None)

    def active_request_count(self):
        with self._lock:
            return len(self._req_state) 

    def active_subscription_count(self):
        with self._lock:
            return len(self._subscriptions) 

    def get_subscription_and_response_no_lock(self, id:RequestId):
        return (self._req_state[id].response if id in self._req_state else None, self._subscriptions[id] if id in self._subscriptions else None)