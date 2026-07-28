"""Commission derivation from a campaign's affiliate configuration.

Pure helpers over the campaign's stored ``affiliate`` JSONB blob (a serialized
:class:`CommissionConfig`, snake_case keys). Commission is computed only for an
attributed conversion that carries a value; refunds reverse it by zeroing the
earned amount on the original conversion (handled by the service).

Kept separate from the postback orchestration because commission rules are their
own concern and will grow (e.g. subscription durations), and because they are
pure and worth testing in isolation.
"""
from __future__ import annotations

from typing import Optional

from app.schemas.campaign.enums import CommissionType


def compute_commission(affiliate: Optional[dict], value: Optional[float]) -> Optional[float]:
    """Earned commission for a single conversion.

    Returns ``None`` when there is no affiliate config or no value to compute on
    (e.g. flat-only campaigns, or an unvalued event). A ``PERCENTAGE`` commission
    is ``value * pct / 100``; a ``FLAT`` commission is a fixed amount per
    conversion.
    """
    if not affiliate or value is None:
        return None

    commission_type = affiliate.get("commission_type")
    commission_value = affiliate.get("commission_value")
    if commission_type is None or commission_value is None:
        return None

    if commission_type == CommissionType.PERCENTAGE.value:
        return round(value * float(commission_value) / 100.0, 2)
    if commission_type == CommissionType.FLAT.value:
        return round(float(commission_value), 2)
    return None
