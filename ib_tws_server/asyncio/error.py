class Error(Exception):
    reason: str
    code: int

    def __init__(self, reason: str, code: int):
        self.reason = reason
        self.code = code
        super().__init__(f"Error Code {code} Reason {reason}")
