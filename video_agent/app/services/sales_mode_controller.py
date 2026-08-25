from __future__ import annotations

from typing import Any

MODE_DISCOVERY = "discovery"
MODE_CONSULTATIVE = "consultative"
MODE_CLOSING = "closing"
MODE_SUPPORT = "support"


def detect_sales_mode(message: str, state: Any) -> str:
    lowered = message.lower()

    support_keywords = (
        "price",
        "cost",
        "services",
        "what do you offer",
        "how does it work",
    )
    if any(keyword in lowered for keyword in support_keywords):
        return MODE_SUPPORT

    closing_keywords = (
        "let's proceed",
        "confirm",
        "okay let's do it",
        "book this",
        "start the project",
    )
    if any(keyword in lowered for keyword in closing_keywords):
        return MODE_CLOSING

    requirement_keywords = (
        "audience",
        "timeline",
        "budget",
        "duration",
        "platform",
        "style",
        "tone",
        "video",
    )
    requirement_count = sum(1 for keyword in requirement_keywords if keyword in lowered)
    if len(lowered) > 80 or requirement_count >= 3:
        return MODE_CONSULTATIVE

    return MODE_DISCOVERY

