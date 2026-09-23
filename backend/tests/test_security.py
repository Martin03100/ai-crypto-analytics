"""Testy pre app/security.py — cisto funkcionalne, bez DB."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.security import (  # noqa: E402
    encrypt_secret, decrypt_secret, generate_reset_token, hash_password,
    hash_reset_token, mask_key, sanitize_text, verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("SuperSecret123")
    assert hashed != "SuperSecret123"
    assert verify_password("SuperSecret123", hashed)
    assert not verify_password("WrongPassword", hashed)


def test_encrypt_decrypt_roundtrip():
    secret = "sk-test-abcdef1234567890"
    encrypted = encrypt_secret(secret)
    assert encrypted != secret
    assert decrypt_secret(encrypted) == secret


def test_mask_key_hides_most_of_the_key():
    masked = mask_key("sk-1234567890abcdef")
    assert masked != "sk-1234567890abcdef"
    assert masked.endswith("cdef") or "..." in masked


def test_generate_reset_token_hash_matches():
    raw, digest = generate_reset_token()
    assert hash_reset_token(raw) == digest
    assert hash_reset_token("something-else") != digest


def test_sanitize_text_strips_control_chars_and_trims():
    dirty = "  hello\x00world\t\n  "
    cleaned = sanitize_text(dirty)
    assert "\x00" not in cleaned
    assert cleaned == cleaned.strip()


def test_sanitize_text_respects_max_length():
    cleaned = sanitize_text("a" * 1000, max_length=10)
    assert len(cleaned) == 10
