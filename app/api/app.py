import dataclasses
import typing

import litestar
import modern_di
import modern_di_litestar
from advanced_alchemy.exceptions import DuplicateKeyError, ForeignKeyError, NotFoundError
from lite_bootstrap import LitestarBootstrapper
from litestar.config.app import AppConfig
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from app import ioc
from app.api import exception_handlers
from app.api.auth import JWTCookieAuthPlugin
from app.api.endpoints import auth as auth_endpoints
from app.api.endpoints import chats as chats_endpoints
from app.api.endpoints import messages as messages_endpoints
from app.exceptions import ConflictError, PermissionDeniedError, ValidationError
from app.settings import settings


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
                ForeignKeyError: exception_handlers.foreign_key_error_handler,
                ValidationError: exception_handlers.validation_error_handler,
                ConflictError: exception_handlers.conflict_error_handler,
            },
            route_handlers=[auth_endpoints.ROUTER, chats_endpoints.ROUTER, messages_endpoints.ROUTER],
            plugins=[
                modern_di_litestar.ModernDIPlugin(di_container, autowired_groups=[ioc.UseCases]),
                JWTCookieAuthPlugin(),
            ],
            request_max_body_size=settings.request_max_body_size,
        ),
        opentelemetry_instrumentors=[
            SQLAlchemyInstrumentor(),
            # True would ship argon2 password hashes, bound as INSERT parameters, to the collector.
            AsyncPGInstrumentor(capture_parameters=False),
        ],
    )
    return LitestarBootstrapper(bootstrap_config=bootstrap_config).bootstrap()
