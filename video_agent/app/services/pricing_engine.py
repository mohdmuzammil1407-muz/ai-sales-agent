from __future__ import annotations

import re
from typing import Any


PRICING_PACKAGES = [
    {
        "type": "Type 1",
        "tier": "Standard",
        "price": 1199,
        "duration": 15,
        "features": [
            "Single character",
            "Social media quality",
            "No script included",
        ],
    },
    {
        "type": "Type 2",
        "tier": "Standard",
        "price": 1899,
        "duration": 30,
        "features": [
            "Single character",
            "Social media quality",
            "No motion graphics",
            "No script included",
        ],
    },
    {
        "type": "Type 3",
        "tier": "Standard",
        "price": 3999,
        "duration": 30,
        "features": [
            "2 characters",
            "Conversation type",
            "Single scene",
            "Social media quality",
        ],
    },
    {
        "type": "Type 5",
        "tier": "Premium",
        "price": 5499,
        "duration": 30,
        "features": [
            "Realistic 3D Product Animation",
            "Ultra HD",
        ],
    },
    {
        "type": "Type 6",
        "tier": "Premium",
        "price": 5999,
        "duration": 30,
        "features": [
            "Food & Restaurant Animation",
            "Ultra HD",
        ],
    },
    {
        "type": "Type 7",
        "tier": "Premium",
        "price": 6999,
        "duration": 30,
        "features": [
            "UGC ads",
            "Ultra HD",
            "Professional Voiceover",
        ],
    },
    {
        "type": "Type 8A",
        "tier": "Premium",
        "price": 9999,
        "duration": 45,
        "features": [
            "Visual storytelling",
            "Brand awareness focus",
        ],
    },
    {
        "type": "Type 8B",
        "tier": "Premium",
        "price": 12999,
        "duration": 60,
        "features": [
            "Visual storytelling",
            "Brand awareness focus",
            "No motion graphics included",
        ],
    },
]


def find_package_by_type(package_type: str) -> dict[str, Any] | None:
    normalized = package_type.strip().lower()
    for package in PRICING_PACKAGES:
        if package["type"].lower() == normalized:
            return package
    return None


def recommend_package(state: Any) -> dict[str, Any] | None:
    budget = getattr(state, "budget", None)
    if budget is None:
        return None

    video_type = (getattr(state, "video_type", "") or "").lower()
    budget_package_type = _package_from_budget(budget, video_type)

    override_package_type = _keyword_override(video_type, budget)
    selected_type = override_package_type or budget_package_type

    if selected_type is None:
        return None
    return find_package_by_type(selected_type)


def requires_escalation(state: Any) -> bool:
    budget = getattr(state, "budget", None)
    if isinstance(budget, int) and budget > 12999:
        return True

    video_type = (getattr(state, "video_type", "") or "").lower()
    if "custom" in video_type:
        return True

    requested_duration = _extract_requested_duration(state)
    if requested_duration is not None and requested_duration > 60:
        return True

    return False


def _package_from_budget(budget: int, video_type: str) -> str | None:
    if budget <= 1500:
        return "Type 1"
    if budget <= 2500:
        return "Type 2"
    if budget <= 4500:
        return "Type 3"
    if budget <= 6000:
        if "food" in video_type:
            return "Type 6"
        return "Type 5"
    if budget <= 8000:
        return "Type 7"
    if budget <= 10000:
        return "Type 8A"
    if budget <= 12999:
        return "Type 8B"
    return None


def _keyword_override(video_type: str, budget: int) -> str | None:
    if "ugc" in video_type:
        return "Type 7"

    if "product" in video_type:
        return "Type 5"

    if "restaurant" in video_type or "food" in video_type:
        return "Type 6"

    if "story" in video_type or "brand" in video_type:
        if budget >= 12999:
            return "Type 8B"
        if budget >= 9999:
            return "Type 8A"

    return None


def _extract_requested_duration(state: Any) -> int | None:
    for attr_name in ("custom_duration", "duration", "timeline"):
        value = getattr(state, attr_name, None)
        duration = _parse_duration_value(value)
        if duration is not None:
            return duration
    return None


def _parse_duration_value(value: Any) -> int | None:
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        match = re.search(r"\b(\d{1,3})\b", value)
        if match:
            return int(match.group(1))

    return None
