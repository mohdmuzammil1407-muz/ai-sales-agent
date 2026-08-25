import re
from typing import Any

from app.models.conversation import ConversationState


MEETING_KEYWORDS = (
    # Exact button values — checked first
    "talk to the team",
    "talk to team",
    "speak to the team",
    "connect with the team",
    "schedule a call",
    "book a call",
    # Generic keywords
    "call",
    "meeting",
    "meet",
    "schedule",
    "book",
    "appointment",
    "human",
    "talk to",
    "speak to",
    "speak with",
    "real person",
    "someone",
    "sales team",
    "your team",
    "zoom",
    "google meet",
    "video call",
    "phone call",
    "consultation",
    "let's talk",
    "want to talk",
    "need to talk",
    "can we talk",
    "can we meet",
    "would love a call",
    "happy to jump on",
    "book a call",
    "set up a call",
    "talk to your team",
    "speak to your team",
    "book another",
    "new meeting",
    "schedule again",
)

WRITTEN_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}


def detect_meeting_intent(user_message: str) -> bool:
    lowered = user_message.lower()
    for keyword in MEETING_KEYWORDS:
        if len(keyword.split()) == 1:
            if re.search(r'\b' + re.escape(keyword) + r'\b', lowered):
                return True
        else:
            if keyword in lowered:
                return True
    return False


def detect_number_selection(user_message: str, max_count: int) -> int | None:
    lowered = user_message.lower().strip()
    if not lowered or max_count <= 0:
        return None

    digit_patterns = (
        r"^\s*(\d+)(?:st|nd|rd|th)?\s*$",
        r"(?:option|slot|number)\s*#?\s*(\d+)\b",
        r"#\s*(\d+)\b",
        r"\bthe\s+(\d+)(?:st|nd|rd|th)?(?:\s+one)?\b",
        r"\b(\d+)(?:st|nd|rd|th)?\s+(?:one|slot)\b",
        r"\b(?:pick|choose|select|book|take)\s+(\d+)\b",
        r"\b(?:go with|i(?:'| wi)?ll take)\s+(\d+)\b",
    )
    for pattern in digit_patterns:
        match = re.search(pattern, lowered)
        if match:
            selection = int(match.group(1))
            if 1 <= selection <= max_count:
                return selection

    for token, value in WRITTEN_NUMBERS.items():
        if re.search(rf"\b{re.escape(token)}\b", lowered) and 1 <= value <= max_count:
            return value

    return None


class StateManager:
    _EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    _BUDGET_PATTERN = re.compile(r"(?:₹\s*|rs\.?\s*)?(\d{3,7})", re.IGNORECASE)
    _DURATION_PATTERN = re.compile(
        r"\b(\d{1,3})\s*(sec|secs|second|seconds|s | m | min|minutes)\b", re.IGNORECASE
    )

    _GENERIC_BUSINESS_LABELS = {
        "Startup Business",
        "Restaurant Business",
        "Brand Business",
    }

    def initialize_state(self, conversation_id: str) -> ConversationState:
        return ConversationState(conversation_id=conversation_id)

    def update_history(self, state: ConversationState, role: str, message: str) -> None:
        state.conversation_history.append({"role": role, "content": message})

    def extract_structured_fields(self, user_message: str) -> dict[str, Any]:
        extracted: dict[str, Any] = {}
        normalized = user_message.strip()
        lowered = normalized.lower()

        name_match = re.search(
            r"\bmy name is\s+([A-Za-z][A-Za-z\s'.-]{0,80})",
            normalized,
            re.IGNORECASE,
        )
        if name_match:
            extracted["name"] = name_match.group(1).split(",")[0].strip()

        email_match = self._EMAIL_PATTERN.search(normalized)
        if email_match:
            extracted["email"] = email_match.group(0)
        else:
            email_label_match = re.search(
                r"\bemail(?:\s+is)?\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
                normalized,
                re.IGNORECASE,
            )
            if email_label_match:
                extracted["email"] = email_label_match.group(1)

        business_match = re.search(
            r"\bbusiness(?:\s+name)?\s+(?:is\s+)?(.+?)(?:,|$)",
            normalized,
            re.IGNORECASE,
        )
        if business_match:
            business_name = business_match.group(1).strip()
            if business_name:
                extracted["business_name"] = business_name

        budget_candidates = [
            int(match.group(1))
            for match in self._BUDGET_PATTERN.finditer(normalized)
            if match.group(1).isdigit()
        ]
        if budget_candidates:
            extracted["budget"] = max(budget_candidates)

        # Duration (video length)
        duration_match = self._DURATION_PATTERN.search(normalized)
        if duration_match:
            extracted["timeline"] = f"{duration_match.group(1)} sec"

        # Delivery timeline (days/weeks)
        days_match = re.search(r"\b(\d{1,3})\s*(day|days)\b", lowered)
        if days_match and "timeline" not in extracted:
            extracted["timeline"] = f"{days_match.group(1)} days"

        week_match = re.search(r"\b(\d{1,2})\s*(week|weeks)\b", lowered)
        if week_match and "timeline" not in extracted:
            extracted["timeline"] = f"{week_match.group(1)} weeks"

        if "asap" in lowered or "urgent" in lowered:
            extracted["timeline"] = "urgent"

        if "next week" in lowered and "timeline" not in extracted:
            extracted["timeline"] = "1 week"

        if "startup" in lowered:
            extracted["business_name"] = "Startup Business"
        elif "restaurant" in lowered:
            extracted["business_name"] = "Restaurant Business"
        elif "brand" in lowered:
            extracted["business_name"] = "Brand Business"

        if "ugc" in lowered:
            extracted["video_type"] = "UGC ad video"
        elif "product" in lowered:
            extracted["video_type"] = "Product video"
        elif "food" in lowered or "restaurant" in lowered:
            extracted["video_type"] = "Food and restaurant video"
        elif "storytelling" in lowered:
            extracted["video_type"] = "Visual storytelling video"

        audience_map = {
            "startup": "Startups",
            "influencer": "Influencers",
            "marketing team": "Marketing Teams",
            "brand": "Brands",
        }
        for token, audience in audience_map.items():
            if token in lowered:
                extracted["target_audience"] = audience
                break

        mood_tokens = []
        mood_map = (
            ("moody", "moody"),
            ("cinematic", "cinematic"),
            ("luxury", "luxury"),
            ("premium", "premium"),
            ("classy", "classy"),
            ("elegant", "elegant"),
            ("bold", "bold"),
            ("dark", "dark"),
            ("gold", "gold-accented"),
            ("minimal", "minimal"),
            ("confident", "confident"),
            ("dramatic", "dramatic"),
            ("high energy", "high-energy"),
            ("soft", "soft"),
            ("warm", "warm"),
        )
        for token, label in mood_map:
            if token in lowered and label not in mood_tokens:
                mood_tokens.append(label)
        if mood_tokens:
            extracted["mood"] = ", ".join(mood_tokens[:4])

        direction_tokens = []
        direction_map = (
            ("close-up", "close-up product framing"),
            ("close up", "close-up product framing"),
            ("slow motion", "slow-motion hero shots"),
            ("quick cuts", "quick-cut transitions"),
            ("product shot", "clean product hero shot"),
            ("dark marble", "luxury surface styling"),
            ("mirror", "mirror styling shot"),
            ("voiceover", "voiceover-led storytelling"),
            ("vo:", "voiceover-led storytelling"),
            ("sfx", "designed cinematic sound"),
            ("brand logo", "centered brand reveal"),
            ("lighting", "intentional lighting direction"),
        )
        for token, label in direction_map:
            if token in lowered and label not in direction_tokens:
                direction_tokens.append(label)
        if direction_tokens:
            extracted["creative_direction"] = ", ".join(direction_tokens[:5])

        return {k: v for k, v in extracted.items() if v is not None}

    def update_state(
        self, state: ConversationState, extracted_data: dict[str, Any]
    ) -> ConversationState:
        for key, value in extracted_data.items():
            if value is None or not hasattr(state, key):
                continue

            current_value = getattr(state, key)
            if current_value is None:
                setattr(state, key, value)
                continue

            if self._is_more_specific(key, current_value, value):
                setattr(state, key, value)

        return state

    def advance_stage(self, state: ConversationState) -> None:
        if state.order_confirmed:
            state.stage = "post_sale"
            return

        if state.stage == "greeting":
            if state.video_type or state.target_audience or state.business_name:
                state.stage = "discovery"
            elif len(state.conversation_history) >= 2:
                state.stage = "discovery"

        elif state.stage == "discovery":
            if state.video_type or state.budget or state.target_audience:
                state.stage = "qualification"

        elif state.stage == "qualification":
            if state.is_fully_qualified():
                state.stage = "recommendation"

        elif state.stage == "recommendation":
            if state.recommended_package:
                state.stage = "closing"

        elif state.stage == "closing":
            if state.order_confirmed:
                state.stage = "post_sale"

    def validate_stage(self, state: ConversationState) -> bool:
        if state.stage == "recommendation" and not state.is_fully_qualified():
            return False
        return True

    def _is_more_specific(self, key: str, old_value: Any, new_value: Any) -> bool:
        if isinstance(old_value, str) and isinstance(new_value, str):
            old_clean = old_value.strip()
            new_clean = new_value.strip()
            if old_clean == new_clean:
                return False
            if key == "business_name":
                return (
                    old_clean in self._GENERIC_BUSINESS_LABELS
                    and new_clean not in self._GENERIC_BUSINESS_LABELS
                ) or len(new_clean) > len(old_clean)
            return len(new_clean) > len(old_clean)

        return False
