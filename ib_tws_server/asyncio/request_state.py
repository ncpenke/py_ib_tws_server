from typing import Union

RequestId = Union[int, str]

class RequestState():
    def __init__(self):
        self.cb = None
        self.response = None
