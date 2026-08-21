class ChatAppError(Exception):
    """Base class for domain errors raised by use cases."""


class PermissionDeniedError(ChatAppError):
    """Raised when an authenticated user may not perform the requested action."""
