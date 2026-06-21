"""Intent classification for Chanakya Copilot."""

from __future__ import annotations

from app.services.copilot.enums.intent import CopilotIntent

_INTENT_KEYWORDS: dict[CopilotIntent, tuple[str, ...]] = {
    CopilotIntent.DAILY_BRIEF: ("brief", "summary", "overview", "portfolio", "today"),
    CopilotIntent.MERCHANT_RISK: ("risk", "fraud", "churn", "flagged"),
    CopilotIntent.FLEET_HEALTH: ("battery", "signal", "network", "reboot", "telemetry", "fleet", "device"),
    CopilotIntent.GMV_TREND: ("trend", "forecast", "predict", "projection", "gmv", "revenue", "growth"),
    CopilotIntent.MERCHANT_PROFILE: ("profile", "merchant", "details", "lookup"),
}


def classify_intent(prompt: str) -> CopilotIntent:
    prompt_lower = prompt.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(keyword in prompt_lower for keyword in keywords):
            return intent
    return CopilotIntent.UNKNOWN
