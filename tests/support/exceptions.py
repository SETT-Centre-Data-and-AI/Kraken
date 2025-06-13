class MissingError(Exception):
    def __init__(self, message: str = "A test file or folder is missing"):
        super().__init__(message)
        self.message = message
