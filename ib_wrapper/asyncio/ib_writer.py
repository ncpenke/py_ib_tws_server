from ibapi.client import EClient
from queue import Queue
from threading import Thread

class IBWriter(Thread):
    def __init__(self, client: EClient):
        super().__init__()
        self.queue = Queue()
        self._client = client

    def run(self):
        while self._client.isConnected():
            self.queue.get()()
