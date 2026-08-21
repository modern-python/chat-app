import typing

import litestar
from litestar import status_codes

from app.exceptions import PermissionDeniedError


if typing.TYPE_CHECKING:
    from advanced_alchemy.exceptions import DuplicateKeyError, NotFoundError


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


def permission_denied_handler(_: object, exc: PermissionDeniedError) -> litestar.Response[dict[str, typing.Any]]:
    return litestar.Response(
        media_type=litestar.MediaType.JSON,
        content={"detail": str(exc) or "Permission denied"},
        status_code=status_codes.HTTP_403_FORBIDDEN,
    )
