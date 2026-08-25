import re

INTENT_HUMAN_REQUEST = "human_request"
INTENT_MEETING_REQUEST = "meeting_request"
INTENT_BUDGET_SHARE = "budget_share"
INTENT_PRICING_QUESTION = "pricing_question"
INTENT_SERVICE_QUESTION = "service_question"
INTENT_GENERAL_CHAT = "general_chat"
INTENT_GREETING = "greeting"
INTENT_BUSINESS_QUERY = "business_query"
INTENT_BUSINESS_FOLLOWUP = "business_followup"

human_keywords = [
    "human",
    "real person",
    "sales agent",
    "representative",
    "talk to someone",
    "connect me",
    "human support",
]

meeting_keywords = [
    "meeting",
    "schedule",
    "book a call",
    "appointment",
    "calendar",
    "talk later",
    "set up a call",
]

budget_share_keywords = [
    "budget is",
    "budget around",
    "budget of",
    "my budget is",
    "can spend",
    "willing to spend",
    "have a budget",
]

# Strictly price-specific keywords — must not match general business/help queries
price_keywords = [
    "price",
    "cost",
    "pricing",
    "how much",
    "package price",
    "charges",
    "rate",
    "rates",
    "discount",
    "bargain",
    "affordable",
    "expensive",
    "fee",
    "rupee",
    "\u20b9",
    "what does it cost",
    "package details",
    "view packages",
    "see packages",
    "packages and pricing",
]

# Kept for backwards compat — same list, no 'offer'/'amount'
price_keywords_legacy = price_keywords

# Broader list used by detect_intent (same strict list)
pricing_keywords = price_keywords

# Business owner / discovery context keywords
business_keywords = [
    "business owner",
    "i own",
    "my business",
    "my company",
    "my brand",
    "my store",
    "my shop",
    "i run",
    "i sell",
    "we sell",
    "our company",
    "our brand",
    "i deal in",
    "i work in",
    "focused on",
    "how can you help",
    "how could you help",
    "what can you offer",
    "what could you offer",
    "how would you help",
    "what do you offer for",
    "help my business",
    "help with my business",
    "help for my business",
    "what could you do for",
    "what can you do for",
    "i make",
    "i create",
    "handmade",
    "i manufacture",
    "i produce",
]

# Follow-up answers to the bot's qualifying question ("what's your main goal?")
# These keywords appear in goal-answer messages and must be routed to the
# consultative LLM path, NOT the generic catch-all or pricing handler.
business_followup_keywords = [
    "increase sales",
    "more sales",
    "grow sales",
    "boost sales",
    "drive sales",
    "brand awareness",
    "build awareness",
    "raise awareness",
    "grow awareness",
    "more audience",
    "reach audience",
    "reach more",
    "wider audience",
    "more customers",
    "get customers",
    "attract customers",
    "grow business",
    "grow my business",
    "grow our business",
    "social media",
    "online presence",
    "more visibility",
    "more reach",
    "drive traffic",
    "conversions",
    "increase revenue",
    "grow revenue",
    "more engagement",
    "more followers",
    "content strategy",
    "video strategy",
    "promote my",
    "promote our",
    "market my",
    "market our",
    "advertise my",
    "advertise our",
]

service_keywords = [
    "services",
    "what do you offer",
    "what can you do",
    "video types",
    "solutions",
    "capabilities",
]


def is_price_query(text: str) -> bool:
    """Returns True only if the user is directly asking about price/cost."""
    normalized = text.lower()
    return any(kw in normalized for kw in price_keywords)


def is_business_query(text: str) -> bool:
    """Returns True if the user is describing their business or asking how we can help them."""
    normalized = text.lower()
    return any(kw in normalized for kw in business_keywords)


def is_business_followup(text: str) -> bool:
    """Returns True if the text looks like an answer to a qualifying business question
    (e.g. 'increase sales', 'brand awareness', 'reach more audience')."""
    normalized = text.lower()
    return any(kw in normalized for kw in business_followup_keywords)

greeting_keywords = [
    "hi",
    "hello",
    "hey",
    "good morning",
    "good evening",
    "how are you",
    "how's it going",
    "whats up",
    "what's up",
]


def _build_phrase_pattern(keyword: str) -> str:
    parts = [re.escape(part) for part in keyword.strip().split()]
    joined = r"\s+".join(parts)
    return rf"(?<!\w){joined}(?!\w)"


def _contains_keyword(message: str, keywords: list[str]) -> bool:
    return any(re.search(_build_phrase_pattern(keyword), message) for keyword in keywords)


def _is_greeting_message(message: str) -> bool:
    normalized = message.strip().lower()
    compact = re.sub(r"[^\w\s']", " ", normalized)
    compact = re.sub(r"\s+", " ", compact).strip()

    if not compact:
        return False

    word_count = len(compact.split())
    if word_count > 8:
        return False

    for keyword in greeting_keywords:
        if re.fullmatch(_build_phrase_pattern(keyword), compact):
            return True
        if re.match(_build_phrase_pattern(keyword), compact) and word_count <= 4:
            return True

    return False


def detect_intent(message: str) -> str:
    normalized = message.lower()

    if len(normalized) <= 40 and _is_greeting_message(normalized):
        return INTENT_GREETING

    if _contains_keyword(normalized, human_keywords):
        return INTENT_HUMAN_REQUEST

    if _contains_keyword(normalized, meeting_keywords):
        return INTENT_MEETING_REQUEST

    if _contains_keyword(normalized, budget_share_keywords):
        return INTENT_BUDGET_SHARE

    # Business follow-up answers (e.g. "increase sales", "brand awareness")
    # must be detected BEFORE the general business_query check, so that they
    # are routed to the follow-up handler which already has conversation context.
    if is_business_followup(normalized) and not is_business_query(normalized):
        return INTENT_BUSINESS_FOLLOWUP

    # Business queries must be checked BEFORE pricing — "what could you offer" contains
    # no price keywords but was previously hijacked by the old broad pricing_keywords list.
    # A business query takes priority over service/general classification.
    if is_business_query(normalized):
        return INTENT_BUSINESS_QUERY

    # Only fire pricing intent if the user is genuinely asking about price/cost
    if is_price_query(normalized):
        return INTENT_PRICING_QUESTION

    if _contains_keyword(normalized, service_keywords):
        return INTENT_SERVICE_QUESTION

    return INTENT_GENERAL_CHAT
