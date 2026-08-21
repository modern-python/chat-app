import dataclasses
import typing

import litestar
import modern_di
import modern_di_litestar
from advanced_alchemy.exceptions import DuplicateKeyError, NotFoundError
from lite_bootstrap import LitestarBootstrapper
from litestar.config.app import AppConfig
from litestar.plugins import InitPlugin
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from app import ioc
from app.api import exception_handlers
from app.api.auth import jwt_cookie_auth
from app.api.endpoints import auth as auth_endpoints
from app.exceptions import PermissionDeniedError
from app.settings import settings
from app.use_cases.authenticate_user import AuthenticateUserUseCase
from app.use_cases.register_user import RegisterUserUseCase


class _JWTCookieAuthPlugin(InitPlugin):
    # AppConfig has no on_app_init field (that hook is a Litestar.__init__-only parameter,
    # unavailable through LitestarBootstrapper's AppConfig -> Litestar.from_config path), and
    # jwt_cookie_auth itself is an unhashable dataclass so it cannot sit in `plugins` directly
    # (PluginRegistry stores plugins in a frozenset). This plugin wrapper is hashable by identity
    # and forwards to jwt_cookie_auth.on_app_init, which Litestar.__init__ calls for every
    # InitPluginProtocol member of `plugins` after the bootstrapper has finished mutating
    # application_config (so openapi_config is already populated by then).
    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        return jwt_cookie_auth.on_app_init(app_config)


def build_app() -> litestar.Litestar:
    di_container: typing.Final = modern_di.Container(groups=ioc.ALL_GROUPS)
    bootstrap_config: typing.Final = dataclasses.replace(
        settings.api_bootstrapper_config,
        application_config=AppConfig(
            exception_handlers={
                NotFoundError: exception_handlers.not_found_error_handler,
                PermissionDeniedError: exception_handlers.permission_denied_handler,
                DuplicateKeyError: exception_handlers.duplicate_key_error_handler,
            },
            route_handlers=[auth_endpoints.ROUTER],
            plugins=[modern_di_litestar.ModernDIPlugin(di_container), _JWTCookieAuthPlugin()],
            dependencies={
                "register_user_use_case": modern_di_litestar.FromDI(RegisterUserUseCase),
                "authenticate_user_use_case": modern_di_litestar.FromDI(AuthenticateUserUseCase),
            },
            request_max_body_size=settings.request_max_body_size,
        ),
        opentelemetry_instrumentors=[
            SQLAlchemyInstrumentor(),
            AsyncPGInstrumentor(capture_parameters=True),
        ],
    )
    return LitestarBootstrapper(bootstrap_config=bootstrap_config).bootstrap()
