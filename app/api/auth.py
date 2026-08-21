import datetime
import typing

import modern_di_litestar
from litestar.config.app import AppConfig
from litestar.connection import ASGIConnection
from litestar.plugins import InitPlugin
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
    try:
        user_id = int(token.sub)
    except ValueError:
        # Token.sub is only guaranteed to be a non-empty string; a malformed/forged subject
        # must fail authentication (401 via the middleware), not crash the request (500).
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
    exclude=[
        # /auth/register and /auth/login opt out via exclude_from_auth=True on the handlers
        # themselves (see app/api/endpoints/auth.py) - that is their one policy home, not here.
        # Litestar joins these into a single alternation and matches with an unanchored findall
        # (litestar/middleware/_utils.py), so each pattern is anchored to the path start to avoid
        # accidentally un-authenticating a future route that merely contains "/docs" or "/health"
        # as a substring (e.g. "/api/chats/{id}/health").
        "^/docs",
        "^/health",
    ],
)


class JWTCookieAuthPlugin(InitPlugin):
    # AppConfig has no on_app_init field (that hook is a Litestar.__init__-only parameter,
    # unavailable through LitestarBootstrapper's AppConfig -> Litestar.from_config path), and
    # jwt_cookie_auth itself is an unhashable dataclass so it cannot sit in `plugins` directly
    # (PluginRegistry stores plugins in a frozenset). This plugin wrapper is hashable by identity
    # and forwards to jwt_cookie_auth.on_app_init, which Litestar.__init__ calls for every
    # InitPluginProtocol member of `plugins` after the bootstrapper has finished mutating
    # application_config (so openapi_config is already populated by then).
    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        return jwt_cookie_auth.on_app_init(app_config)
