import pytest

from app.config.settings import Settings, get_settings


def test_settings_reads_database_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_HOST", "db.example.com")
    monkeypatch.setenv("DATABASE_PORT", "5433")
    monkeypatch.setenv("DATABASE_USERNAME", "appuser")
    monkeypatch.setenv("DATABASE_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_NAME", "soundbox")

    cfg = Settings()
    assert cfg.database_host == "db.example.com"
    assert cfg.database_port == 5433
    assert cfg.database_username == "appuser"
    assert cfg.database_password == "secret"
    assert cfg.database_name == "soundbox"


def test_warehouse_uri_from_gcs_bucket(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    monkeypatch.setenv("WAREHOUSE_PATH", "")
    monkeypatch.setenv("GCS_BUCKET", "my-lakehouse-bucket")
    cfg = Settings()
    assert cfg.warehouse_uri == "gs://my-lakehouse-bucket"


def test_require_database_raises_when_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_HOST", "")
    cfg = Settings()
    with pytest.raises(RuntimeError, match="DATABASE_HOST"):
        cfg.require_database()


def test_gcs_config_from_env(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    monkeypatch.setenv("GCS_BUCKET", "test-bucket")
    monkeypatch.setenv("WAREHOUSE_PATH", "gs://test-bucket/soundbox")
    cfg = Settings()
    cfg.require_gcs()
    assert cfg.warehouse_uri == "gs://test-bucket/soundbox"
