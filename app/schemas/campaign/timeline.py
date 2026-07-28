"""Timeline block (spec §3 step 10).

Only the always-present dates live here; the marketplace-only application window
and join type live on :class:`MarketplaceSourcing`. Cross-block ordering
(submission ≤ liveStart) is checked at the top-level model where both are visible.
"""
from __future__ import annotations

from datetime import date

from pydantic import model_validator

from app.schemas.campaign.common import CampaignBaseModel


class Timeline(CampaignBaseModel):
    content_submission_deadline: date
    live_start: date
    live_end: date

    @model_validator(mode="after")
    def _order(self) -> "Timeline":
        if self.live_end < self.live_start:
            raise ValueError("liveEnd must be on or after liveStart.")
        if self.content_submission_deadline > self.live_start:
            raise ValueError("contentSubmissionDeadline must be on or before liveStart.")
        return self