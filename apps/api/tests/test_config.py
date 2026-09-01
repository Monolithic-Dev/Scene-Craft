import pytest

from src.core.config import Settings


def test_default_placeholder_secret_is_allowed_in_development():
    settings = Settings(environment="development", _env_file=None)
    assert settings.jwt_secret_key == "CHANGE_ME_IN_PRODUCTION_VIA_SECRET_MANAGER"


def test_default_placeholder_secret_is_rejected_outside_development():
    with pytest.raises(ValueError, match="insecure placeholder"):
        Settings(environment="production", _env_file=None)


def test_a_real_secret_is_accepted_outside_development():
    settings = Settings(environment="production", jwt_secret_key="a-real-secret", _env_file=None)
    assert settings.jwt_secret_key == "a-real-secret"
