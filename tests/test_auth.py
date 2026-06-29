import pytest
from jose import JWTError

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    plain = "mypassword123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_jwt_token_flow():
    payload = {"sub": "user@example.com", "role": "employee", "department": "general"}
    token = create_access_token(payload)
    assert isinstance(token, str)
    assert len(token) > 0

    # Decode and verify
    decoded = decode_access_token(token)
    assert decoded["sub"] == "user@example.com"
    assert decoded["role"] == "employee"
    assert decoded["department"] == "general"
    assert "exp" in decoded


def test_jwt_invalid_token():
    with pytest.raises(JWTError):
        decode_access_token("invalid-token-string")
