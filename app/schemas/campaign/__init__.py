"""Campaign schemas: four discriminated unions + simple blocks + derivations.

Spec map (see CAMPAIGN_CREATION.md):
    track.py        §1/§3  Track union (Awareness | Performance)  [union #1]
    sourcing.py     §2/§3  Sourcing union (Marketplace | BYOC)    [union #2]
    promotion.py    §5     Promotion union (Physical | App | SaaS) [union #3]
    compensation.py §3.11  Compensation union (Flat|Affiliate|Hybrid) [union #4]
    fulfillment.py  §3.7   Fulfillment union (Product|Sub|Service|None)
    audience/creative/compliance/timeline.py — simple blocks
    metrics.py      §6     metric catalog & derived sets
    derived.py      §8     server-derived values + attribution profile
    requests.py            CampaignCreate (top-level + cross-block §7)
    responses.py           response models
"""
from app.schemas.campaign.requests import CampaignCreate
from app.schemas.campaign.responses import (
    CampaignCreatedResponse,
    CampaignListItem,
    CampaignListResponse,
    CampaignResponse,
    DraftResponse,
)
from app.schemas.campaign.derived import AttributionProfile, CampaignDerived

__all__ = [
    "CampaignCreate",
    "CampaignResponse",
    "CampaignCreatedResponse",
    "CampaignListItem",
    "CampaignListResponse",
    "DraftResponse",
    "AttributionProfile",
    "CampaignDerived",
]