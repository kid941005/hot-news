import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.db.database import hash_password, verify_password


def test_verify_password_accepts_pbkdf2_hash():
    stored = hash_password("secret")

    assert verify_password("secret", stored)
    assert not verify_password("wrong", stored)


def test_verify_password_accepts_legacy_sha256_hash():
    import hashlib

    stored = hashlib.sha256("secret".encode()).hexdigest()

    assert verify_password("secret", stored)
    assert not verify_password("wrong", stored)
