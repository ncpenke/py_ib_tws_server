class Error:
    reason: str
    code: int

    def __init__(self, reason: str, code: int):
        self.reason = reason
        self.code = code
