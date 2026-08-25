from __future__ import annotations

import re
from typing import Any


def calculate_lead_score(state: Any) -> int:
    score = 0

    budget = getattr(state, "budget", None)
    if budget:
        if budget >= 10000:
            score += 4
        elif budget >= 6000:
            score += 3
        elif budget >= 4000:
            score += 2
        else:
            score += 1

    timeline = (getattr(state, "timeline", "") or "").lower()
    if "urgent" in timeline or "asap" in timeline:
        score += 3

    days = _extract_days(timeline)
    if days is not None and days <= 14:
        score += 2

    recommended_package = (getattr(state, "recommended_package", "") or "").strip()
    if recommended_package.startswith(("Type 5", "Type 6", "Type 7", "Type 8")):
        score += 3

    if getattr(state, "business_name", None) is not None:
        score += 1

    return score


def is_high_priority(score: int) -> bool:
    return score >= 7


def can_auto_close(state: Any) -> bool:
    is_fully_qualified = getattr(state, "is_fully_qualified", None)
    fully_qualified = bool(callable(is_fully_qualified) and is_fully_qualified())

    budget = getattr(state, "budget", None)
    recommended_package = getattr(state, "recommended_package", None)
    order_confirmed = getattr(state, "order_confirmed", False)

    return (
        fully_qualified
        and recommended_package is not None
        and budget is not None
        and budget <= 12999
        and order_confirmed is False
    )


def confirm_order(state: Any) -> dict[str, str | None]:
    state.order_confirmed = True
    return {
        "status": "confirmed",
        "package": getattr(state, "recommended_package", None),
        "next_step": "Project onboarding initiated",
    }


def _extract_days(timeline: str) -> int | None:
    day_match = re.search(r"\b(\d{1,3})\s*day", timeline)
    if day_match:
        return int(day_match.group(1))

    week_match = re.search(r"\b(\d{1,2})\s*week", timeline)
    if week_match:
        return int(week_match.group(1)) * 7

    return None
