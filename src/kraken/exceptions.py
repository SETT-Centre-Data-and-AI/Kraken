class UnstructuredDataFrameError(Exception):
    """Custom exception for empty and unstructured (no columns in DataFrame) DataFrame."""

    def __init__(
        self, message: str = "DataFrame is unstructured, i.e. no columns in DataFrame."
    ):
        self.message = message
        super().__init__(self.message)


class CredentialError(Exception):
    def __init__(self, message: str = "A Kraken CredentialError has occurred"):
        super().__init__(message)
        self.message = message


class DatabaseConnectionError(Exception):
    def __init__(self, message: str = "A Kraken DatabaseConnectionError has occurred"):
        super().__init__(message)
        self.message = message


class QueryExecutionError(Exception):
    def __init__(self, message: str = "A Kraken QueryExecutionError has occurred"):
        super().__init__(message)
        self.message = message


class CommitError(Exception):
    def __init__(self, message: str = "A Kraken CommitError has occurred"):
        super().__init__(message)
        self.message = message


class DuplicateColumnError(Exception):
    def __init__(self, message: str = "A Kraken DuplicateColumnError has occurred"):
        super().__init__(message)
        self.message = message


class VarcharLengthError(Exception):
    def __init__(self, message: str = "A Kraken VarcharLengthError has occurred"):
        super().__init__(message)
        self.message = message


class UploadError(Exception):
    def __init__(self, message: str = "A Kraken UploadError has occurred"):
        super().__init__(message)
        self.message = message


class UploadConflictError(UploadError):
    def __init__(self, message: str = "A Kraken UploadError has occurred"):
        super().__init__(message)
        self.message = message
