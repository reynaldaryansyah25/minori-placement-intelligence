"""Domain-level persistence outcomes without infrastructure exception imports."""


class RecordNotFoundError(LookupError):
    """A requested aggregate was not found for an update."""


class BusinessConflictError(ValueError):
    """The requested action conflicts with the current business state."""
