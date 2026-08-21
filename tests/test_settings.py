import pytest

from app.settings import INSECURE_JWT_SECRET, Settings


def test_db_dsn_parsed_exposes_driver() -> None:
    settings = Settings(db_dsn="postgresql+asyncpg://user:pw@host/dbname")
    assert settings.db_dsn_parsed.drivername == "postgresql+asyncpg"
    assert settings.db_dsn_parsed.database == "dbname"


def test_api_bootstrapper_config_carries_service_identity() -> None:
    settings = Settings(service_name="svc", service_version="9.9.9")
    config = settings.api_bootstrapper_config
    assert config.service_name == "svc"
    assert config.service_version == "9.9.9"


def test_ensure_jwt_secret_is_configured_allows_the_default_secret_locally() -> None:
    Settings(service_environment="local").ensure_jwt_secret_is_configured()


def test_ensure_jwt_secret_is_configured_allows_a_real_secret_outside_local() -> None:
    Settings(service_environment="production", jwt_secret="a-real-secret").ensure_jwt_secret_is_configured()  # noqa: S106


def test_ensure_jwt_secret_is_configured_rejects_the_default_secret_outside_local() -> None:
    # jwt_secret set explicitly (rather than left to the JWT_SECRET env var, which the test
    # container sets) to isolate this test from the environment it happens to run in.
    settings = Settings(service_environment="production", jwt_secret=INSECURE_JWT_SECRET)
    with pytest.raises(RuntimeError, match="jwt_secret"):
        settings.ensure_jwt_secret_is_configured()
