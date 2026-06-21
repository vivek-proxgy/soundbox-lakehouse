"""Intent classification logic for Chanakya Copilot."""

from __future__ import annotations


def classify_intent(prompt: str) -> str:
    """Classify user query intent to route context gathering."""
    prompt_lower = prompt.lower()
    if any(k in prompt_lower for k in ["brief", "summary", "overview", "portfolio", "today"]):
        return "daily_brief"
    if any(k in prompt_lower for k in ["risk", "fraud", "churn", "flagged"]):
        return "merchant_risk"
    if any(k in prompt_lower for k in ["battery", "signal", "network", "reboot", "telemetry", "fleet", "device"]):
        return "fleet_health"
    if any(k in prompt_lower for k in ["trend", "forecast", "predict", "projection", "gmv", "revenue", "growth"]):
        return "gmv_trend"
    if any(k in prompt_lower for k in ["profile", "merchant", "details", "lookup"]):
        return "merchant_profile"
    return "unknown"
