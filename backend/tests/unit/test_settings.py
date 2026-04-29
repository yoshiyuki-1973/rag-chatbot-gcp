import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_top_k_default_must_be_at_least_one():
    with pytest.raises(ValidationError):
        Settings(TOP_K_DEFAULT=0, _env_file=None)


def test_top_k_default_must_be_at_most_twenty():
    with pytest.raises(ValidationError):
        Settings(TOP_K_DEFAULT=21, _env_file=None)


def test_top_k_default_accepts_api_bounds():
    settings = Settings(TOP_K_DEFAULT=20, _env_file=None)

    assert settings.top_k_default == 20


def test_db_pool_size_accepts_safe_defaults():
    settings = Settings(_env_file=None)

    assert settings.db_pool_min_size == 1
    assert settings.db_pool_max_size == 3


def test_db_pool_size_must_be_at_least_one():
    with pytest.raises(ValidationError):
        Settings(DB_POOL_MIN_SIZE=0, _env_file=None)


def test_db_pool_size_must_not_exceed_supavisor_session_limit():
    with pytest.raises(ValidationError):
        Settings(DB_POOL_MAX_SIZE=16, _env_file=None)
