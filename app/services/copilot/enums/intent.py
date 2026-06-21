from __future__ import annotations

from enum import StrEnum


class CopilotIntent(StrEnum):
    DAILY_BRIEF = "daily_brief"
    MERCHANT_PROFILE = "merchant_profile"
    MERCHANT_RISK = "merchant_risk"
    FLEET_HEALTH = "fleet_health"
    GMV_TREND = "gmv_trend"
    UNKNOWN = "unknown"
