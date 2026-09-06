import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import auth as api_module


def test_login_rate_limit_blocks_after_max_attempts():
    api_module._LOGIN_ATTEMPTS.clear()
    try:
        for _ in range(api_module.LOGIN_MAX_ATTEMPTS):
            assert api_module._is_login_rate_limited("203.0.113.10") is False
            api_module._record_login_attempt("203.0.113.10")
        assert api_module._is_login_rate_limited("203.0.113.10") is True
    finally:
        api_module._LOGIN_ATTEMPTS.clear()


def test_login_rate_limit_clears_after_success():
    api_module._LOGIN_ATTEMPTS.clear()
    try:
        api_module._record_login_attempt("203.0.113.11")
        api_module._clear_login_attempts("203.0.113.11")
        assert api_module._is_login_rate_limited("203.0.113.11") is False
    finally:
        api_module._LOGIN_ATTEMPTS.clear()
