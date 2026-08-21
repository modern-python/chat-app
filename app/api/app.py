import dataclasses
import typing

import litestar
import modern_di
import modern_di_litestar
from advanced_alchemy.exceptions import NotFoundError
from lite_bootstrap import LitestarBootstrapper
from litestar.config.app import AppConfig
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from app import ioc
from app.api import exception_handlers
from app.exceptions import PermissionDeniedError
from app.settings import settings


def build_app() -> litestar.Litestar:
    di_container: typing.Final = modern_di.Container(groups=ioc.ALL_GROUPS)
    bootstrap_config: typing.Final = dataclasses.replace(
        settings.api_bootstrapper_config,
        application_config=AppConfig(
            exception_handlers={
                NotFoundError: exception_handlers.not_found_error_handler,
                PermissionDeniedError: exception_handlers.permission_denied_handler,
            },
            route_handlers=[],
            plugins=[modern_di_litestar.ModernDIPlugin(di_container)],
            dependencies={},
            request_max_body_size=settings.request_max_body_size,
        ),
        opentelemetry_instrumentors=[
            SQLAlchemyInstrumentor(),
            AsyncPGInstrumentor(capture_parameters=True),
        ],
    )
    return LitestarBootstrapper(bootstrap_config=bootstrap_config).bootstrap()
