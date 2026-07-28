"""Metric catalog & derived metric sets (spec §6).

``kpi_targets`` is a map of ``metric_id -> target number``; only metrics that
exist in :data:`METRIC_CATALOG` are accepted. The derived-set helpers mirror
the frontend's "what this campaign measures" panel so analytics can reuse them.

NOTE (per current scope): Leads is descoped — Performance always means Sales.
Lead-only metrics are omitted from the catalog and derived sets.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MetricTier(str, Enum):
    CONTENT = "CONTENT"      # platform-sourced
    CLICK = "CLICK"          # our redirect
    VERIFIED = "VERIFIED"    # needs integration


class MetricSource(str, Enum):
    PLATFORM = "PLATFORM"
    REDIRECT = "REDIRECT"
    INTEGRATION = "INTEGRATION"


@dataclass(frozen=True)
class MetricMeta:
    label: str
    unit: str
    fmt: str
    source: MetricSource
    tier: MetricTier


# metric_id -> metadata (spec §6 table; lead-only metrics dropped per scope).
METRIC_CATALOG: dict[str, MetricMeta] = {
    "reach": MetricMeta("Reach", "count", "integer", MetricSource.PLATFORM, MetricTier.CONTENT),
    "impressions": MetricMeta("Impressions", "count", "integer", MetricSource.PLATFORM, MetricTier.CONTENT),
    "engagement": MetricMeta("Engagements", "count", "integer", MetricSource.PLATFORM, MetricTier.CONTENT),
    "engagementRate": MetricMeta("Engagement rate", "percent", "percent", MetricSource.PLATFORM, MetricTier.CONTENT),
    "views": MetricMeta("Views", "count", "integer", MetricSource.PLATFORM, MetricTier.CONTENT),
    "cpm": MetricMeta("CPM", "currency", "currency", MetricSource.PLATFORM, MetricTier.CONTENT),
    "emv": MetricMeta("Earned media value", "currency", "currency", MetricSource.PLATFORM, MetricTier.CONTENT),
    "sharesSaves": MetricMeta("Shares & saves", "count", "integer", MetricSource.PLATFORM, MetricTier.CONTENT),
    "clicks": MetricMeta("Clicks", "count", "integer", MetricSource.REDIRECT, MetricTier.CLICK),
    "uniqueClicks": MetricMeta("Unique clicks", "count", "integer", MetricSource.REDIRECT, MetricTier.CLICK),
    "ctr": MetricMeta("CTR", "percent", "percent", MetricSource.REDIRECT, MetricTier.CLICK),
    "cpc": MetricMeta("CPC", "currency", "currency", MetricSource.REDIRECT, MetricTier.CLICK),
    "geo": MetricMeta("Geo breakdown", "category", "text", MetricSource.REDIRECT, MetricTier.CLICK),
    "device": MetricMeta("Device breakdown", "category", "text", MetricSource.REDIRECT, MetricTier.CLICK),
    "orders": MetricMeta("Orders", "count", "integer", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "revenue": MetricMeta("Revenue", "currency", "currency", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "roas": MetricMeta("ROAS", "multiplier", "multiplier", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "cpa": MetricMeta("CPA", "currency", "currency", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "aov": MetricMeta("Average order value", "currency", "currency", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "conversionRate": MetricMeta("Conversion rate", "percent", "percent", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "codeRedemptions": MetricMeta("Code redemptions", "count", "integer", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "installs": MetricMeta("Installs", "count", "integer", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "inAppPurchases": MetricMeta("In-app purchases", "count", "integer", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "cpi": MetricMeta("Cost per install", "currency", "currency", MetricSource.INTEGRATION, MetricTier.VERIFIED),
    "commissionOwed": MetricMeta("Commission owed", "currency", "currency", MetricSource.INTEGRATION, MetricTier.VERIFIED),
}

KNOWN_METRIC_IDS: frozenset[str] = frozenset(METRIC_CATALOG)

# Content baseline shown for every campaign.
_CONTENT_BASELINE = ("reach", "impressions", "engagement", "engagementRate")
# Click baseline once a destination/redirect exists.
_CLICK_BASELINE = ("clicks", "uniqueClicks", "ctr", "cpc", "geo", "device")


def headline_metrics(*, performance: bool, mobile_app: bool) -> tuple[str, ...]:
    """Headline KPI ids (spec §6 ``headlineKpi``). Leads descoped."""
    if not performance:
        return ("reach", "impressions")
    if mobile_app:
        return ("installs", "cpi")
    return ("roas", "revenue")  # sales (web/physical)


def sales_verified_metrics(*, mobile_app: bool) -> tuple[str, ...]:
    if mobile_app:
        return ("installs", "inAppPurchases", "revenue", "roas", "cpa", "cpi", "commissionOwed")
    return ("orders", "revenue", "roas", "cpa", "aov", "conversionRate", "codeRedemptions", "commissionOwed")


def measured_metric_ids(*, performance: bool, mobile_app: bool, has_destination: bool) -> list[str]:
    """The full set of metrics a campaign can surface (spec §6 derived sets)."""
    ids: list[str] = list(_CONTENT_BASELINE) + ["views", "cpm", "emv", "sharesSaves"]
    if performance:
        ids += list(_CLICK_BASELINE)
        ids += list(sales_verified_metrics(mobile_app=mobile_app))
    elif has_destination:
        ids.append("clicks")
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for m in ids:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out
