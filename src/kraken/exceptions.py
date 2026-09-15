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


class GraphingError(ValueError):
    """Base exception for anticipated Kraken graphing failures."""


class GraphCapabilityError(GraphingError):
    """Raised when a graph or requested graph feature is not supported."""


class GraphColumnError(GraphingError):
    """Raised when a required graph column is missing or has a conflicting role."""


class GraphDataTypeError(GraphingError):
    """Raised when a graph column has an unsupported dtype."""


class GraphConversionError(GraphDataTypeError):
    """Raised when Kraken cannot convert a graph column to its required dtype."""


class GraphAggregationError(GraphingError):
    """Raised for invalid or unsupported graph aggregation requests."""


class GraphDataError(GraphingError):
    """Raised when graph input data cannot produce the requested result."""


class TimelineDataError(GraphDataError):
    """Raised when timeline start/end values are missing or invalid."""


class InsufficientGraphDataError(GraphDataError):
    """Raised when there are insufficient usable observations for a graph."""


class GraphRenderingError(GraphingError):
    """Raised for anticipated failures while rendering prepared graph data."""


class GraphExportError(GraphingError):
    """Raised when a prepared graph cannot be exported."""


class GraphExportDependencyError(GraphExportError, RuntimeError):
    """Raised when graph export requires an unavailable external dependency."""
