class BridgeError(RuntimeError):
    """Base class for bridge errors."""


class BridgeDisconnected(BridgeError):
    pass


class BridgeProtocolError(BridgeError):
    pass


class BridgeRejected(BridgeError):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message or code
        super().__init__(f"{code}: {self.message}")


class WrongBuild(BridgeRejected):
    pass
