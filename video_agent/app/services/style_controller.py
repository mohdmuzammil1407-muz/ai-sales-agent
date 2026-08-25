STYLE_DIRECT = "direct"
STYLE_CASUAL = "casual"
STYLE_ANALYTICAL = "analytical"
STYLE_PROFESSIONAL = "professional"
STYLE_NEUTRAL = "neutral"


def detect_user_style(message: str) -> str:
    normalized = message.lower()

    if len(normalized) < 15:
        return STYLE_DIRECT

    casual_phrases = ["hey", "hi", "bro", "cool", "nice"]
    if any(phrase in normalized for phrase in casual_phrases):
        return STYLE_CASUAL

    business_terms = ["strategy", "marketing", "campaign", "audience"]
    if any(term in normalized for term in business_terms):
        return STYLE_PROFESSIONAL

    if len(normalized) > 120:
        return STYLE_ANALYTICAL

    return STYLE_NEUTRAL
