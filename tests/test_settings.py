from app.settings import Settings


def test_db_dsn_parsed_exposes_driver() -> None:
    settings = Settings(db_dsn="postgresql+asyncpg://user:pw@host/dbname")
    assert settings.db_dsn_parsed.drivername == "postgresql+asyncpg"
    assert settings.db_dsn_parsed.database == "dbname"


def test_api_bootstrapper_config_carries_service_identity() -> None:
    settings = Settings(service_name="svc", service_version="9.9.9")
    config = settings.api_bootstrapper_config
    assert config.service_name == "svc"
    assert config.service_version == "9.9.9"
