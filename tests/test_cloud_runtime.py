from faq_agent import config


def test_cloud_settings_are_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("RAG_TARGET", "cloud")
    monkeypatch.setenv("VECTOR_URL", "http://127.0.0.1:6334")
    monkeypatch.setenv("CATALOG_PATH", "local.sqlite3")
    monkeypatch.setenv("QDRANT_CLOUD_URL", "https://example.aws.cloud.qdrant.io")
    monkeypatch.setenv("QDRANT_CLOUD_API_KEY", "test-only")
    config.get_settings.cache_clear()
    try:
        cloud = config.get_settings()
        assert cloud.catalog_path == str(tmp_path / ".local/cloud/library.sqlite3")
        assert cloud.vector_url == "https://example.aws.cloud.qdrant.io"
        monkeypatch.setenv("RAG_TARGET", "local")
        config.get_settings.cache_clear()
        local = config.get_settings()
        assert local.vector_url == "http://127.0.0.1:6334"
        assert local.catalog_path == "local.sqlite3"
    finally:
        config.get_settings.cache_clear()


def test_invalid_cloud_profile_does_not_fall_back(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("RAG_TARGET", "cloud")
    monkeypatch.setenv("QDRANT_CLOUD_URL", "http://localhost:6334")
    monkeypatch.setenv("QDRANT_CLOUD_API_KEY", "test-only")
    config.get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="Cloud target requires"):
            config.get_settings()
    finally:
        config.get_settings.cache_clear()
