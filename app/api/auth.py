import datetime
import typing

import modern_di_litestar
from litestar.connection import ASGIConnection
from litestar.security.jwt import JWTCookieAuth, Token

from app import ioc
from app.database import resources as database_resources
from app.database import tables
from app.settings import settings


async def retrieve_user_handler(token: Token, connection: ASGIConnection) -> tables.UsersTable | None:
    # Auth middleware runs before request-scoped DI is available, so resolve the app-scoped
    # engine and open a short-lived session through the same factory the container uses. That
    # factory sets join_transaction_mode="create_savepoint", which is what keeps the per-test
    # rollback fixture intact when the engine provider is overridden with a live connection.
    di_container: typing.Final = modern_di_litestar.fetch_di_container(connection.app)
    engine: typing.Final = di_container.resolve_provider(ioc.Database.database_engine)
    session: typing.Final = database_resources.create_session(engine)
    try:
        return await session.get(tables.UsersTable, int(token.sub))
    finally:
        await database_resources.close_session(session)


jwt_cookie_auth: typing.Final = JWTCookieAuth[tables.UsersTable](
    retrieve_user_handler=retrieve_user_handler,
    token_secret=settings.jwt_secret,
    default_token_expiration=datetime.timedelta(seconds=settings.jwt_lifetime_seconds),
    exclude=[
        "/api/auth/register",
        "/api/auth/login",
        "/health",
        "/docs",
        "/metrics",
    ],
)
