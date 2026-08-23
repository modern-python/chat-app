import datetime
import typing

import litestar
from litestar.config.app import AppConfig
from litestar.connection import ASGIConnection
from litestar.plugins import InitPlugin
from litestar.security.jwt import JWTCookieAuth, Token

from app.actor import Actor
from app.settings import settings


type AuthedRequest = litestar.Request[Actor, Token, typing.Any]


async def retrieve_user_handler(token: Token, _connection: ASGIConnection) -> Actor | None:
    try:
        return Actor(id=int(token.sub))
    except ValueError:
        return None


jwt_cookie_auth: typing.Final = JWTCookieAuth[Actor](
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
