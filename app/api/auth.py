import datetime as dt
import typing
import uuid

import litestar
import modern_di
from litestar.config.app import AppConfig
from litestar.connection import ASGIConnection
from litestar.plugins import InitPlugin
from litestar.security.jwt import JWTCookieAuth, Token
from modern_di_litestar import fetch_di_container

from app import ioc
from app.actor import Actor
from app.settings import settings


type AuthedRequest = litestar.Request[Actor, Token, typing.Any]


async def retrieve_user_handler(token: Token, _connection: ASGIConnection) -> Actor | None:
    try:
        return Actor(id=int(token.sub))
    except ValueError:
        return None


async def revoked_token_handler(token: Token, connection: ASGIConnection) -> bool:
    async with fetch_di_container(connection.app).build_child_container(scope=modern_di.Scope.REQUEST) as container:
        check_token_revoked: typing.Final = container.resolve_provider(ioc.UseCases.check_token_revoked_use_case)
        return await check_token_revoked(jti=str(token.jti))


def new_token_id() -> str:
    return str(uuid.uuid4())


jwt_cookie_auth: typing.Final = JWTCookieAuth[Actor](
    retrieve_user_handler=retrieve_user_handler,
    revoked_token_handler=revoked_token_handler,
    require_claims=["jti"],
    token_secret=settings.jwt_secret,
    default_token_expiration=dt.timedelta(seconds=settings.jwt_lifetime_seconds),
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
