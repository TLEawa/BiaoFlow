class SheetFlowError(Exception):
    """Base error that is safe to summarize for end users."""


class ConfigurationError(SheetFlowError):
    pass


class InputFileError(SheetFlowError):
    pass


class OperationError(SheetFlowError):
    pass


class ExportError(SheetFlowError):
    pass


class TaskCancelled(SheetFlowError):
    pass
