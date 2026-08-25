from __future__ import annotations

import random

OBJECTION_PRICE_HIGH = "price_high"
OBJECTION_NEED_TIME = "need_time"
OBJECTION_NEED_APPROVAL = "need_approval"
OBJECTION_WANT_EXAMPLES = "want_examples"
OBJECTION_UNSURE = "unsure"
OBJECTION_COMPETITOR = "competitor"
OBJECTION_QUALITY_DOUBT = "quality_doubt"
OBJECTION_NONE = "none"

price_keywords: list[str] = [
    "expensive",
    "too much",
    "high price",
    "costly",
    "budget is low",
    "can you reduce",
    "discount",
    "cheaper",
    "price is high",
    "not affordable",
]

time_keywords: list[str] = [
    "let me think",
    "will decide later",
    "need time",
    "not sure yet",
    "i'll get back",
    "maybe later",
    "thinking about it",
]

approval_keywords: list[str] = [
    "need to check",
    "ask my partner",
    "need approval",
    "discuss with team",
    "check with boss",
    "consult someone",
]

examples_keywords: list[str] = [
    "show examples",
    "portfolio",
    "previous work",
    "samples",
    "can i see",
    "any samples",
    "past projects",
]

unsure_keywords: list[str] = [
    "not sure",
    "confused",
    "don't know",
    "not decided",
    "exploring options",
    "just looking",
]

competitor_keywords: list[str] = [
    "other studio",
    "competitor",
    "another company",
    "someone else",
    "cheaper elsewhere",
    "other options",
]

quality_keywords: list[str] = [
    "ai looks fake",
    "realistic",
    "will it look good",
    "professional enough",
    "trust",
    "doubt",
    "will this look real",
    "will it look real",
    "look fake",
    "looks fake",
    "is it realistic",
    "is this realistic",
    "does it look professional",
    "will it look professional",
]

OBJECTION_RESPONSES: dict[str, list[str]] = {
    OBJECTION_PRICE_HIGH: [
        "Our pricing reflects the quality of AI-powered cinematic production — significantly more cost-effective than traditional video shoots. That said, we do have packages starting from ₹1199 if you'd like to start smaller and test the quality first.",
        "The value comes from the production quality — Ultra HD, AI-enhanced visuals, and fast delivery. Would you like to see what our entry-level package looks like?",
        "We keep our pricing competitive for the quality delivered. If budget is a concern, we can suggest a starting package that still looks professional on social media."
    ],
    OBJECTION_NEED_TIME: [
        "Of course, take your time. Just to let you know, timelines are usually booked in advance - I can tentatively hold your slot while you decide.",
        "No rush. Would it help if I sent a quick summary of what we discussed so you can review it?",
        "Completely understandable. Most clients finalize within a day or two. Is there anything specific you'd like me to clarify before you decide?",
    ],
    OBJECTION_NEED_APPROVAL: [
        "Makes sense. Would you like me to prepare a quick summary of the package so you can share it with your team?",
        "No problem. I can also arrange a short call if your partner or manager wants to discuss the project directly.",
        "Sure. Once you've checked, just come back here and we can move forward quickly.",
    ],
    OBJECTION_WANT_EXAMPLES: [
        "You can check our portfolio and previous work at studios.ilmoraai.com. It showcases different video styles we've produced.",
        "Our website has examples of food promos, product animations and brand storytelling videos. Would any specific style be helpful to look at?",
    ],
    OBJECTION_UNSURE: [
        "That's completely fine. A lot of clients start by just exploring. Tell me roughly what you're promoting and I can suggest a direction.",
        "No problem. What kind of business or product are you working with? That'll help me point you in the right direction.",
    ],
    OBJECTION_COMPETITOR: [
        "Totally fair to compare options. What sets us apart is the AI-powered production combined with cinematic quality - most alternatives offer one or the other, not both.",
        "If you've seen pricing elsewhere, I'd be happy to show you what's included in our packages so you can make a clear comparison.",
    ],
    OBJECTION_QUALITY_DOUBT: [
        "That's a valid question. Our output is Ultra HD and uses AI to enhance realism, not replace it. The final result is production-grade quality.",
        "You can browse our portfolio at studios.ilmoraai.com to judge the quality directly before committing to anything.",
    ],
}


def detect_objection(message: str) -> str:
    lowered_message = message.lower()

    checks: list[tuple[str, list[str]]] = [
        (OBJECTION_PRICE_HIGH, price_keywords),
        (OBJECTION_NEED_TIME, time_keywords),
        (OBJECTION_NEED_APPROVAL, approval_keywords),
        (OBJECTION_WANT_EXAMPLES, examples_keywords),
        (OBJECTION_UNSURE, unsure_keywords),
        (OBJECTION_COMPETITOR, competitor_keywords),
        (OBJECTION_QUALITY_DOUBT, quality_keywords),
    ]

    for objection_type, keywords in checks:
        if any(keyword in lowered_message for keyword in keywords):
            return objection_type

    return OBJECTION_NONE


def get_objection_response(objection_type: str) -> str | None:
    responses = OBJECTION_RESPONSES.get(objection_type)
    if responses:
        return random.choice(responses)
    return None
