import typing

import litestar
from litestar import status_codes
from litestar.di import NamedDependency
from litestar.exceptions import NotAuthorizedException
from litestar.response import Response

from app.api.auth import jwt_cookie_auth
from app.database import tables
from app.schemas import api as schemas
from app.use_cases.authenticate_user import AuthenticateUserUseCase
from app.use_cases.register_user import RegisterUserUseCase


@litestar.post("/auth/register/", status_code=status_codes.HTTP_201_CREATED, exclude_from_auth=True)
async def register(
    data: schemas.RegisterRequest,
    register_user_use_case: NamedDependency[RegisterUserUseCase],
) -> Response[schemas.User]:
    user: typing.Final = await register_user_use_case(data)
    return jwt_cookie_auth.login(
        identifier=str(user.id),
        response_body=schemas.User.model_validate(user),
        response_status_code=status_codes.HTTP_201_CREATED,
    )


@litestar.post("/auth/login/", status_code=status_codes.HTTP_200_OK, exclude_from_auth=True)
async def login(
    data: schemas.LoginRequest,
    authenticate_user_use_case: NamedDependency[AuthenticateUserUseCase],
) -> Response[schemas.User]:
    user: typing.Final = await authenticate_user_use_case(data.username, data.password)
    if user is None:
        raise NotAuthorizedException(detail="Invalid username or password")
    return jwt_cookie_auth.login(
        identifier=str(user.id),
        response_body=schemas.User.model_validate(user),
        response_status_code=status_codes.HTTP_200_OK,
    )


@litestar.post("/auth/logout/", status_code=status_codes.HTTP_204_NO_CONTENT)
async def logout() -> Response[None]:
    response: typing.Final = Response(content=None, status_code=status_codes.HTTP_204_NO_CONTENT)
    response.delete_cookie(jwt_cookie_auth.key)
    return response


@litestar.get("/auth/me/")
async def me(request: litestar.Request[tables.UsersTable, typing.Any, typing.Any]) -> schemas.User:
    return schemas.User.model_validate(request.user)


ROUTER: typing.Final = litestar.Router(
    path="/api",
    route_handlers=[register, login, logout, me],
)
