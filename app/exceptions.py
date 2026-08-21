class ChatAppError(Exception):
    """Base class for domain errors raised by use cases."""


class PermissionDeniedError(ChatAppError):
    """Raised when an authenticated user may not perform the requested action."""


class ValidationError(ChatAppError):
    """Raised when a request is well-formed but violates a domain invariant."""


class ConflictError(ChatAppError):
    """Raised when an otherwise-authorized request conflicts with the resource's current state."""
