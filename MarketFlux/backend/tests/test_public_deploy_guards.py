"""Guards for a public demo deploy. These do not need Mongo or network."""
import pytest

from copilot_code_tool import run_python
from redis_settings import build_redis_url
from runtime_config import (
    allowed_origins,
    code_sandbox_enabled,
    copilot_daily_turn_cap,
    is_development,
    localhost_origin_regex,
    require_mongo_url,
)


def test_unset_environment_is_not_development(monkeypatch):
    monkeypatch.delenv("MARKETFLUX_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    assert is_development() is False
    assert localhost_origin_regex() is None


def test_explicit_test_env_is_development(monkeypatch):
    monkeypatch.setenv("MARKETFLUX_ENV", "test")
    assert is_development() is True
    assert localhost_origin_regex() is not None


def test_production_requires_allowed_origins(monkeypatch):
    monkeypatch.setenv("MARKETFLUX_ENV", "production")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        allowed_origins()


def test_production_does_not_add_localhost(monkeypatch):
    monkeypatch.setenv("MARKETFLUX_ENV", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://marketflux.vercel.app")
    assert allowed_origins() == ["https://marketflux.vercel.app"]


def test_missing_mongo_url_explains_why(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    with pytest.raises(RuntimeError, match="MongoDB is still required"):
        require_mongo_url()


def test_code_sandbox_off_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_CODE_SANDBOX", raising=False)
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert code_sandbox_enabled() is False
    result = run_python("print(pd.read_csv('/etc/passwd'))")
    assert result["ok"] is False
    assert "disabled" in result["error"].lower()


def test_demo_mode_forces_sandbox_off(monkeypatch):
    monkeypatch.setenv("ENABLE_CODE_SANDBOX", "true")
    monkeypatch.setenv("DEMO_MODE", "true")
    assert code_sandbox_enabled() is False
    result = run_python("print(1)")
    assert result["ok"] is False


def test_enabled_sandbox_blocks_pandas_and_numpy_io(monkeypatch):
    monkeypatch.setenv("ENABLE_CODE_SANDBOX", "true")
    monkeypatch.delenv("DEMO_MODE", raising=False)
    samples = [
        "print(pd.read_csv('/etc/passwd'))",
        "np.save('/tmp/x.npy', np.array([1]))",
        "print(np.load('/etc/passwd'))",
    ]
    for code in samples:
        result = run_python(code)
        assert result["ok"] is False, code
        assert "not allowed" in result["error"]


def test_demo_daily_cap_defaults_lower(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.delenv("COPILOT_DAILY_TURNS", raising=False)
    assert copilot_daily_turn_cap() == 20


def test_redis_url_wins_and_keeps_tls(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "rediss://:secret@cache.example:6380/2")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    assert build_redis_url() == "rediss://:secret@cache.example:6380/2"


def test_redis_legacy_host_fallback(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_HOST", "redis.internal")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_PASSWORD", "p@ss")
    monkeypatch.delenv("REDIS_DB", raising=False)
    assert build_redis_url() == "redis://:p%40ss@redis.internal:6380/0"
