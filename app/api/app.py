import dataclasses
import typing

import litestar
import modern_di
import modern_di_litestar
from advanced_alchemy.exceptions import DuplicateKeyError, NotFoundError
from lite_bootstrap import LitestarBootstrapper
from litestar.config.app import AppConfig
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from app import ioc
from app.api import exception_handlers
from app.api.auth import JWTCookieAuthPlugin
from app.api.endpoints import auth as auth_endpoints
from app.api.endpoints import chats as chats_endpoints
from app.exceptions import PermissionDeniedError
from app.settings import settings
from app.use_cases.authenticate_user import AuthenticateUserUseCase
from app.use_cases.create_chat import CreateChatUseCase
from app.use_cases.fetch_chat import FetchChatUseCase
from app.use_cases.register_user import RegisterUserUseCase


def build_app() -> litestar.Litestar:
    settings.ensure_jwt_secret_is_configured()
    di_container: typing.Final = modern_di.Container(groups=ioc.ALL_GROUPS)
    bootstrap_config: typing.Final = dataclasses.replace(
        settings.api_bootstrapper_config,
        application_config=AppConfig(
            exception_handlers={
                NotFoundError: exception_handlers.not_found_error_handler,
                PermissionDeniedError: exception_handlers.permission_denied_handler,
                DuplicateKeyError: exception_handlers.duplicate_key_error_handler,
            },
            route_handlers=[auth_endpoints.ROUTER, chats_endpoints.ROUTER],
            plugins=[modern_di_litestar.ModernDIPlugin(di_container), JWTCookieAuthPlugin()],
            dependencies={
                "register_user_use_case": modern_di_litestar.FromDI(RegisterUserUseCase),
                "authenticate_user_use_case": modern_di_litestar.FromDI(AuthenticateUserUseCase),
                "create_chat_use_case": modern_di_litestar.FromDI(CreateChatUseCase),
                "fetch_chat_use_case": modern_di_litestar.FromDI(FetchChatUseCase),
            },
            request_max_body_size=settings.request_max_body_size,
        ),
        opentelemetry_instrumentors=[
            SQLAlchemyInstrumentor(),
            # False: bound query parameters include argon2 password hashes (every registration
            # INSERTs one) - capturing them would ship credential material to the OTel collector.
            AsyncPGInstrumentor(capture_parameters=False),
        ],
    )
    return LitestarBootstrapper(bootstrap_config=bootstrap_config).bootstrap()
