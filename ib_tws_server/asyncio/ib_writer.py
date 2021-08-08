from ibapi.client import EClient
import math
from queue import Queue
from threading import Thread
import time

class IBWriter(Thread):
    MAX_REQS_PER_SECOND = 30

    """
    Sends messages to TWS in a dedicated thread to avoid blocking the asyncio thread
    Also enforces message throttling
    """
    def __init__(self, client: EClient):
        super().__init__()
        self.queue = Queue()
        self._client = client
        self._last_msg_time_sec = math.floor(time.time())
        self._enable_message_throttling = True
        self._requests_in_last_sec = 0
    
    def enforce_msg_rate(self):
        if not self._enable_message_throttling:
            return

        cur_time_sec = math.floor(time.time())
        if (cur_time_sec == self._last_msg_time_sec):
            if self._requests_in_last_sec > IBWriter.MAX_REQS_PER_SECOND:
                time.sleep(1)
                self.enforce_msg_rate()
                return
            else:
                self._requests_in_last_sec += 1
        else:
            self._last_msg_time_sec = cur_time_sec
            self._requests_in_last_sec = 1

    def run(self):
        while self._client.isConnected():
            req = self.queue.get()
            self.enforce_msg_rate()
            req()
