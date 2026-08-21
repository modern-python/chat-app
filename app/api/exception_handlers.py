import typing

import litestar
from litestar import status_codes

from app.exceptions import ConflictError, PermissionDeniedError, ValidationError


if typing.TYPE_CHECKING:
    from advanced_alchemy.exceptions import DuplicateKeyError, ForeignKeyError, NotFoundError


def not_found_error_handler(_: object, __: NotFoundError) -> litestar.Response[dict[str, typing.Any]]:
    return litestar.Response(
        media_type=litestar.MediaType.JSON,
        content={"detail": "Not found"},
        status_code=status_codes.HTTP_404_NOT_FOUND,
    )


def duplicate_key_error_handler(_: object, __: DuplicateKeyError) -> litestar.Response[dict[str, typing.Any]]:
    return litestar.Response(
        media_type=litestar.MediaType.JSON,
        content={"detail": "Conflict"},
        status_code=status_codes.HTTP_409_CONFLICT,
    )


def foreign_key_error_handler(_: object, __: ForeignKeyError) -> litestar.Response[dict[str, typing.Any]]:
    return litestar.Response(
        media_type=litestar.MediaType.JSON,
        # Constant detail, not str(exc): the underlying integrity error can carry bound
        # parameter values (e.g. ids from other tables) that shouldn't be echoed back verbatim.
        content={"detail": "Invalid reference"},
        status_code=status_codes.HTTP_400_BAD_REQUEST,
    )


def permission_denied_handler(_: object, exc: PermissionDeniedError) -> litestar.Response[dict[str, typing.Any]]:
    return litestar.Response(
        media_type=litestar.MediaType.JSON,
        content={"detail": str(exc) or "Permission denied"},
        status_code=status_codes.HTTP_403_FORBIDDEN,
    )


def validation_error_handler(_: object, exc: ValidationError) -> litestar.Response[dict[str, typing.Any]]:
    return litestar.Response(
        media_type=litestar.MediaType.JSON,
        content={"detail": str(exc) or "Validation error"},
        status_code=status_codes.HTTP_400_BAD_REQUEST,
    )


def conflict_error_handler(_: object, exc: ConflictError) -> litestar.Response[dict[str, typing.Any]]:
    return litestar.Response(
        media_type=litestar.MediaType.JSON,
        content={"detail": str(exc) or "Conflict"},
        status_code=status_codes.HTTP_409_CONFLICT,
    )
