import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import main


def test_cleanup_expired_tokens_removes_only_expired_tokens():
    old_tokens = main._tokens.copy()
    now = datetime.now()
    try:
        main._tokens.clear()
        main._tokens["expired"] = (1, now - timedelta(seconds=1))
        main._tokens["active"] = (2, now + timedelta(seconds=60))

        removed = main.cleanup_expired_tokens(now)

        assert removed == 1
        assert "expired" not in main._tokens
        assert main._tokens["active"][0] == 2
    finally:
        main._tokens.clear()
        main._tokens.update(old_tokens)
