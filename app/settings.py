import typing

import pydantic_settings
from lite_bootstrap import LitestarConfig
from sqlalchemy.engine.url import URL, make_url


# >= 32 bytes: PyJWT warns (InsecureKeyLengthWarning) below that for HS256.
INSECURE_JWT_SECRET: typing.Final = "insecure-local-secret-do-not-use-in-prod"


class Settings(pydantic_settings.BaseSettings):
    service_name: str = "chat-app"
    service_version: str = "1.0.0"
    service_environment: str = "local"
    # echo/echo_pool log bound parameters, including password_hash on every registration.
    service_debug: bool = False
    log_level: str = "info"

    db_dsn: str = "postgresql+asyncpg://postgres:password@db/postgres"
    db_pool_size: int = 5
    db_max_overflow: int = 0
    db_pool_pre_ping: bool = True

    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = 8000

    jwt_secret: str = INSECURE_JWT_SECRET
    jwt_lifetime_seconds: int = 60 * 60 * 24 * 7
    # False so local http:// development still gets the cookie; production must set True.
    jwt_cookie_secure: bool = False

    opentelemetry_endpoint: str = ""
    sentry_dsn: str = ""
    logging_buffer_capacity: int = 0
    swagger_offline_docs: bool = True

    cors_allowed_origins: list[str] = []
    cors_allowed_methods: list[str] = ["*"]
    cors_allowed_headers: list[str] = ["*"]
    cors_exposed_headers: list[str] = []

    request_max_body_size: int = 1024 * 1024

    def ensure_jwt_secret_is_configured(self) -> None:
        if self.service_environment != "local" and self.jwt_secret == INSECURE_JWT_SECRET:
            message = (
                f"jwt_secret is still the insecure default while service_environment="
                f"{self.service_environment!r}; set the JWT_SECRET environment variable."
            )
            raise RuntimeError(message)

    @property
    def db_dsn_parsed(self) -> URL:
        return make_url(self.db_dsn)

    @property
    def sync_db_dsn_parsed(self) -> URL:
        # Alembic drives psycopg2, not asyncpg.
        return self.db_dsn_parsed.set(drivername="postgresql")

    @property
    def api_bootstrapper_config(self) -> LitestarConfig:
        return LitestarConfig(
            service_name=self.service_name,
            service_version=self.service_version,
            service_environment=self.service_environment,
            service_debug=self.service_debug,
            opentelemetry_endpoint=self.opentelemetry_endpoint,
            sentry_dsn=self.sentry_dsn,
            cors_allowed_origins=self.cors_allowed_origins,
            cors_allowed_methods=self.cors_allowed_methods,
            cors_allowed_headers=self.cors_allowed_headers,
            cors_exposed_headers=self.cors_exposed_headers,
            logging_buffer_capacity=self.logging_buffer_capacity,
            swagger_offline_docs=self.swagger_offline_docs,
        )


settings = Settings()
