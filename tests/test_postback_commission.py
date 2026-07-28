"""Commission derivation (pure)."""
from __future__ import annotations

from app.services.commission import compute_commission


def test_percentage_commission():
    affiliate = {"commission_type": "PERCENTAGE", "commission_value": 12}
    assert compute_commission(affiliate, 1000.0) == 120.0


def test_flat_commission_is_fixed_per_conversion():
    affiliate = {"commission_type": "FLAT", "commission_value": 50}
    assert compute_commission(affiliate, 1000.0) == 50.0
    assert compute_commission(affiliate, 5.0) == 50.0


def test_no_affiliate_config_returns_none():
    assert compute_commission(None, 1000.0) is None
    assert compute_commission({}, 1000.0) is None


def test_no_value_returns_none():
    affiliate = {"commission_type": "PERCENTAGE", "commission_value": 12}
    assert compute_commission(affiliate, None) is None


def test_unknown_type_returns_none():
    assert compute_commission({"commission_type": "WAT", "commission_value": 1}, 100.0) is None


def test_percentage_rounds_to_two_places():
    affiliate = {"commission_type": "PERCENTAGE", "commission_value": 7.5}
    assert compute_commission(affiliate, 33.33) == round(33.33 * 7.5 / 100, 2)
