import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_settings_keep_safe_local_defaults():
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.secret_key == "change-me-in-production"


def test_production_accepts_strong_secret_and_debug_disabled():
    settings = Settings(
        _env_file=None,
        environment="production",
        secret_key="a-strong-production-secret-with-more-than-32-chars",
        debug=False,
    )
    assert settings.environment == "production"


@pytest.mark.parametrize(
    "secret_key",
    [
        "short",
        "change-me-in-production",
        "replace-with-a-long-random-secret-before-deployment",
        "your-secret-value-that-is-long-enough-to-pass",
    ],
)
def test_production_rejects_weak_or_placeholder_secrets(secret_key):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            secret_key=secret_key,
            debug=False,
        )


def test_production_rejects_debug_mode():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            secret_key="a-strong-production-secret-with-more-than-32-chars",
            debug=True,
        )


@pytest.mark.parametrize("expiry", [0, -1, 10081])
def test_rejects_unsafe_token_expiry(expiry):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, access_token_expire_minutes=expiry)


def test_normalizes_environment_name():
    settings = Settings(_env_file=None, environment=" PRODUCTION ", secret_key="a-strong-production-secret-with-more-than-32-chars")
    assert settings.environment == "production"
