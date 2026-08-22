import datetime
import typing

import litestar
import modern_di_litestar
from litestar.config.app import AppConfig
from litestar.connection import ASGIConnection
from litestar.plugins import InitPlugin
from litestar.security.jwt import JWTCookieAuth, Token

from app import ioc
from app.database import resources as database_resources
from app.database import tables
from app.settings import settings


type AuthedRequest = litestar.Request[tables.UsersTable, Token, typing.Any]


async def retrieve_user_handler(token: Token, connection: ASGIConnection) -> tables.UsersTable | None:
    # Auth middleware runs before request-scoped DI exists, so this opens its own session.
    try:
        user_id = int(token.sub)
    except ValueError:
        return None
    di_container: typing.Final = modern_di_litestar.fetch_di_container(connection.app)
    engine: typing.Final = di_container.resolve_provider(ioc.Database.database_engine)
    session: typing.Final = database_resources.create_session(engine)
    try:
        return await session.get(tables.UsersTable, user_id)
    finally:
        await database_resources.close_session(session)


jwt_cookie_auth: typing.Final = JWTCookieAuth[tables.UsersTable](
    retrieve_user_handler=retrieve_user_handler,
    token_secret=settings.jwt_secret,
    default_token_expiration=datetime.timedelta(seconds=settings.jwt_lifetime_seconds),
    secure=settings.jwt_cookie_secure,
    # Anchored: Litestar matches the joined patterns with an unanchored findall.
    exclude=[
        "^/docs",
        "^/health",
        "^/static",
        "^/metrics",
    ],
)


class JWTCookieAuthPlugin(InitPlugin):
    # jwt_cookie_auth is an unhashable dataclass, so it cannot go in `plugins` itself.
    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        return jwt_cookie_auth.on_app_init(app_config)
