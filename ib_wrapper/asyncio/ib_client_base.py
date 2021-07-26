from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ib_wrapper.asyncio.ib_writer import IBWriter
from threading import Lock, Thread
from typing import Callable, Dict, Generic, List, Type, TypeVar

ResponseType = TypeVar("ResponseType")
class SingleRequestCallbackState(Generic[ResponseType]):
    response: ResponseType
    cb: Callable[[ResponseType], None]

    def __init__(self, cb):
        self.cb = cb
        self.response = ResponseType()

SingleRequestState = Dict[int, SingleRequestCallbackState[ResponseType]]

class GlobalRequestState(Generic[ResponseType]):
    response: ResponseType
    cbs: List[Callable[[ResponseType], None]]

    def __init__(self):
        self.cbs = []
        self.response = None

SingleStreamingRequestState = Dict[int, Callable[[ResponseType], None]]
GlobalStreamingRequestState = List[Callable[[ResponseType], None]]

class IBClientBase(EClient,EWrapper):
    _lock: Lock

    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self._writer = IBWriter(self)
        self._lock = Lock()
        self._current_request_id = 0

    def run(self):
        self._writer.start()
        EClient.run(self)

    def next_request_id(self):
        with self._lock:
            self._current_request_id += 1
            return self._current_request_id

    def connectionClosed(self):
        self._writer.queue.put(lambda *a, **k: None)

    def dispatch_global_request_cbs(self, e: GlobalRequestState[ResponseType]):
        cbs = None
        res = None
        with self._lock:
            cbs = e.cbs
            e.cbs = []
            res = e.response
        for c in cbs:
            c(res)

    def start(self, host: str, port: int, client_id: int):
        self.connect(host, port, client_id)
        thread = Thread(target = self.run)
        thread.start()
        setattr(thread, "_thread", thread)

