"""HMAC signing primitive — the security-critical core, tested in isolation.

Covers the spec's security checklist for the signature/timestamp layer:
valid passes, tampered body fails, wrong secret fails, stale/future timestamp
fails, and the comparison is constant-time (no early-return on mismatch).
"""
from __future__ import annotations

import hmac

import pytest

from app.core import postback_signing as sign

SECRET = "a" * 64          # stand-in for a 32-byte hex secret
BODY = b'{"event_type":"purchase","order_id":"ORD-1","value":10,"currency":"INR"}'
TS = "1750000000"


def test_valid_signature_passes():
    sig = sign.compute_signature(SECRET, TS, BODY)
    assert sign.verify_signature(SECRET, TS, BODY, sig) is True


def test_tampered_body_fails():
    sig = sign.compute_signature(SECRET, TS, BODY)
    tampered = BODY.replace(b'"value":10', b'"value":1000')
    assert sign.verify_signature(SECRET, TS, tampered, sig) is False


def test_wrong_secret_fails():
    sig = sign.compute_signature(SECRET, TS, BODY)
    assert sign.verify_signature("b" * 64, TS, BODY, sig) is False


def test_tampered_timestamp_fails_signature():
    sig = sign.compute_signature(SECRET, TS, BODY)
    assert sign.verify_signature(SECRET, "1750000001", BODY, sig) is False


def test_empty_or_garbage_signature_fails():
    assert sign.verify_signature(SECRET, TS, BODY, "") is False
    assert sign.verify_signature(SECRET, TS, BODY, "not-a-hex-sig") is False


def test_signature_is_hex_sha256_length():
    sig = sign.compute_signature(SECRET, TS, BODY)
    assert len(sig) == 64 and all(c in "0123456789abcdef" for c in sig)


# --- timestamp window -------------------------------------------------------


def test_timestamp_within_tolerance():
    now = 1750000000.0
    assert sign.timestamp_within_tolerance("1750000000", 300, now=now) is True
    assert sign.timestamp_within_tolerance("1749999800", 300, now=now) is True  # 200s old


def test_stale_timestamp_rejected():
    now = 1750000000.0
    assert sign.timestamp_within_tolerance("1749999000", 300, now=now) is False  # 1000s old


def test_future_timestamp_rejected():
    now = 1750000000.0
    assert sign.timestamp_within_tolerance("1750001000", 300, now=now) is False  # 1000s ahead


def test_non_numeric_timestamp_rejected():
    assert sign.timestamp_within_tolerance("not-a-number", 300, now=1750000000.0) is False


# --- constant-time comparison ----------------------------------------------


def test_uses_constant_time_compare(monkeypatch):
    """Verification must route through hmac.compare_digest (constant-time), not
    use ``==`` which short-circuits on the first differing byte."""
    calls = {"n": 0}
    real = hmac.compare_digest

    def spy(a, b):
        calls["n"] += 1
        return real(a, b)

    monkeypatch.setattr(sign.hmac, "compare_digest", spy)
    sig = sign.compute_signature(SECRET, TS, BODY)
    sign.verify_signature(SECRET, TS, BODY, sig)
    assert calls["n"] == 1


def test_equal_length_single_byte_diff_fails():
    sig = sign.compute_signature(SECRET, TS, BODY)
    # Flip the last hex char -> same length, one byte different.
    flipped = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    assert sign.verify_signature(SECRET, TS, BODY, flipped) is False
