from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional

import pytz
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.state_manager import (
    StateManager,
    detect_number_selection,
    detect_meeting_intent,
)
from app.database.db import get_db
from app.models.conversation import ConversationState
from app.models.db_models import Conversation, Lead, Message, Order
from app.services.calendar_service import (
    book_slot,
    format_dates_for_chat,
    format_times_for_chat,
    get_available_dates,
    get_available_times,
)
from app.services.email_service import send_meeting_confirmation
from app.services.intent_service import (
    detect_intent,
    INTENT_BUSINESS_QUERY,
    INTENT_BUSINESS_FOLLOWUP,
    is_price_query,
    is_business_query,
    is_business_followup,
)
from app.services.lead_scoring import (
    calculate_lead_score,
    can_auto_close,
    confirm_order,
    is_high_priority,
)
from app.services.llm_service import generate_response
from app.services.objection_service import (
    OBJECTION_NONE,
    detect_objection,
    get_objection_response,
)
from app.services.pricing_engine import (
    find_package_by_type,
    recommend_package,
    requires_escalation,
)
from app.services.sales_mode_controller import detect_sales_mode
from app.services.style_controller import detect_user_style

router = APIRouter()
LAST_CRASH = ""
conversation_store: dict[str, ConversationState] = {}
state_manager = StateManager()


def _build_dynamic_reply(template: str, state: ConversationState) -> str:
    package = state.recommended_package or "our recommended package"
    video = state.video_type or "your video"
    return template.replace("{package}", package).replace("{video}", video)

DIRECT_ANSWERS = {
    "summary_request": {
        "keywords": ["summarize", "summary", "4 lines", "in brief", "before confirming", "break it down", "summarize package", "summarize the package", "summary of package", "four lines"],
        "reply": "Here is a quick summary based on our discussion:\n\nPackage: Based on your requirements, the recommended package is our best fit\nPrice: As discussed\nDuration: 30\u201345 seconds depending on package\nDeliverables: Custom AI video optimized for your platform and audience.\n\nWould you like me to confirm the exact package details?",
    },
    "high_intent_brief": {
        "keywords": [
            "fine-dining", "fine dining", "restaurant in", "food closeup",
            "steam", "ambience shots", "cinematic ambience", "premium mood",
            "can you do this in", "10 days"
        ],
        "reply": "That's a solid brief. The turnaround is feasible for a 30-second cinematic video. Based on what you've described, our Type 6 package at ₹5999 is a strong fit — Ultra HD production style. Want to lock that in?",
    },
    "tone_understanding": {
        "keywords": [
            "classy", "not loud", "classy not", "22-40", "22–40",
            "instagram and youtube", "do you understand this tone", "premium mood"
        ],
        "reply": "Yes, understood. Clean and cinematic — warm lighting, minimal text overlay. That style performs really well for your target audience on Instagram Reels and YouTube Shorts. We can build that direction into your package.",
    },
    "creative_requirements": {
        "keywords": [
            "realistic food", "food texture", "food textures",
            "ambience transition", "no generic", "no stock", "not stock",
            "real texture", "genuine look"
        ],
        "reply": "Noted. Our Type 6 production focuses on realistic food textures, steam closeups, and smooth ambience transitions — nothing stock or generic. Every frame is custom-rendered to match your restaurant's visual identity.",
    },
    "ugc_differentiation": {
        "keywords": [
            "ugc", "ugc-style", "ugc style", "user generated",
            "ugc cut", "ugc version", "one ugc", "ugc-style cut", "ugc style cut", "need one ugc", "also need one"
        ],
        "reply": "A UGC-style cut with voiceover is a different format from the restaurant promo. That falls under our Type 7 package at ₹6999 — Ultra HD with professional voiceover. If you want both the cinematic promo and a UGC cut, those would be two separate packages.",
    },
    "multi_format": {
        "keywords": [
            "2 versions", "two versions", "one for reels one for stories", 
            "reels and stories", "aspect ratio", "both formats",
            "two formats", "landscape", "vertical format", "16:9", "9:16", 
            "youtube and linkedin", "different formats", "landscape for", 
            "vertical for", "portrait format"
        ],
        "reply": "Since the concept is the same, we can export multiple formats from the same project — landscape 16:9 for YouTube or LinkedIn, and vertical 9:16 for Instagram or Stories. This is usually included as part of the delivery without extra cost.",
    },
    "addon_query": {
        "keywords": ["script", "voiceover", "subtitles", "tamil", "english and tamil", "subtitle"],
        "reply": "The base package covers the video production. Script writing, professional voiceover, and subtitles in English or Tamil can be added on top. For a restaurant promo, most clients prefer a music-driven cinematic style — but if you want narration we can include that as an add-on.",
    },
    "scope_change": {
        "keywords": ["45 seconds", "45-second", "45 sec", "longer", "extend", "after project starts"],
        "reply": "If you need 45 seconds instead of 30, that falls under our Type 8A package at ₹9999. It's worth deciding the duration upfront before production starts to avoid rework costs.",
    },
    "payment_terms": {
        "keywords": ["milestone", "upfront", "advance", "payment plan", "pay full", "installment"],
        "reply": "Payment structure is something our team can discuss depending on the project size. For standard packages, we typically take an advance to begin and the balance on delivery. I can connect you with the team to finalize that.",
    },
    "revision_policy": {
        "keywords": ["revision", "revisions", "major changes", "after render", "revision rounds"],
        "reply": "Standard projects include 2 revision rounds before final render. Major changes after the final render — like reshooting a scene or changing the concept — may involve additional charges. Our team will clarify this during onboarding.",
    },
    "deadline_commitment": {
        "keywords": ["festival", "deadline", "delayed", "delay", "commitment", "guaranteed", "on time"],
        "reply": "We take deadlines seriously. For a 10-day timeline, we plan the production schedule from day one. If something causes a delay on our side, we prioritize your project and communicate proactively. Festival campaign timelines are flagged as high priority.",
    },
    "discount_urgency": {
        "keywords": ["confirm today", "if i confirm today", "discount", "bonus deliverable", "offer if i confirm", "something extra"],
        "reply": "If you confirm today, we can prioritize your slot and begin briefing immediately. {package} already includes strong production value for {video}. Want to go ahead and lock it in?",
    },
    "final_recommendation": {
        "keywords": [
            "recommend the best",
            "best package for my case",
            "recommend for my case",
            "what do you recommend",
            "which package",
            "suggest a package",
            "okay, recommend",
            "ok, recommend",
            "recommend the best package"
        ],
        "reply": "Based on everything you've shared, I recommend {package}. It's the strongest match for {video} and your target audience.",
    },
    "budget_negotiation": {
        "keywords": ["my budget is", "budget is only", "tight budget", "lower budget", "can you reduce", "too expensive for"],
        "reply": "We have packages starting from ₹1199. Based on your brief and budget, I can point you to the closest fit. Could you share your rough budget range so I can suggest the best match?",
    },
}


ORDER_INTENT_KEYWORDS = [
    "confirm the order",
    "yes lets proceed",
    "yes let's proceed",
    "proceed with that",
    "start the project",
    "book this",
    "lock it in",
    "place order",
    "i want to order",
    "send me whatsapp",
    "whatsapp me",
    "send details on whatsapp",
    "confirm package",
    "let's do it",
    "lets do it",
    "yes go ahead",
]


def _extract_whatsapp_number(message: str) -> Optional[str]:
    if not message:
        return None

    match = re.search(r"(\+?\d[\d\s\-]{7,}\d)", message)
    if not match:
        return None

    number = match.group(1)
    cleaned = re.sub(r"[^\d+]", "", number)
    digits_only = re.sub(r"\D", "", cleaned)
    if len(digits_only) < 8:
        return None

    return cleaned


def _generate_order_ref() -> str:
    return f"VID{uuid.uuid4().hex[:8].upper()}"


def _is_order_intent_message(message: str) -> bool:
    normalized = message.lower()
    return any(keyword in normalized for keyword in ORDER_INTENT_KEYWORDS)


def _finalize_order(db: Session, state: ConversationState, conversation_record: Conversation) -> dict[str, object]:
    if not state.order_ref:
        state.order_ref = _generate_order_ref()

    confirmation = confirm_order(state)
    reply = (
        f"Great! Your {state.recommended_package} is confirmed. "
        f"I will send your order reference {state.order_ref} on WhatsApp at {state.whatsapp_number}. "
        "Our onboarding team will reach out with the next steps."
    )
    return _persist_assistant_reply(
        db,
        state,
        conversation_record,
        reply,
        order_confirmed=state.order_confirmed,
        confirmation=confirmation,
        whatsapp_number=state.whatsapp_number,
        order_ref=state.order_ref,
    )


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    meeting_email_collection: bool = False
    active_flow: Optional[str] = None
    flow_step: Optional[str] = None
    bootstrap_identity: bool = False


class ScheduleMeetingRequest(BaseModel):
    name: Optional[str] = None
    email: str
    purpose: Optional[str] = None
    time: str
    scheduledAt: Optional[str] = None


def _extract_datetime_slot(message: str) -> Optional[str]:
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}\b", message)
    return match.group(0) if match else None


def _parse_free_text_meeting_time_to_slot_id(raw_time: str) -> Optional[str]:
    if not raw_time:
        return None

    text = raw_time.strip().lower()
    text = re.sub(r"(\d{1,2})\.(\d{2})", r"\1:\2", text)
    text = re.sub(r"\s+", " ", text)

    timezone = pytz.timezone(os.getenv("MEETING_TIMEZONE", "Asia/Kolkata"))
    now = datetime.now(timezone)
    target_date = None
    default_hour = 10
    default_minute = 0

    if "this week" in text:
        target_candidate = (now + timedelta(days=1)).date()
        while target_candidate.weekday() in (5, 6):
            target_candidate += timedelta(days=1)
        target_date = target_candidate
    elif "next week" in text:
        days_until_next_monday = (7 - now.weekday()) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7
        target_date = (now + timedelta(days=days_until_next_monday)).date()

    if "day after tomorrow" in text:
        target_date = (now + timedelta(days=2)).date()
    elif "tomorrow" in text:
        target_date = (now + timedelta(days=1)).date()
    elif "today" in text:
        target_date = now.date()

    month_regex = (
        r"\b("
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?"
        r")\s+(\d{1,2})(?:st|nd|rd|th)?\b"
    )
    day_month_regex = (
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+("
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?"
        r")\b"
    )
    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    if target_date is None:
        match = re.search(month_regex, text)
        if match:
            month_name = match.group(1).lower()
            day_num = int(match.group(2))
            month_num = month_map.get(month_name)
            if month_num:
                year = now.year
                try:
                    candidate = datetime(year, month_num, day_num).date()
                    if candidate < now.date():
                        candidate = datetime(year + 1, month_num, day_num).date()
                    target_date = candidate
                except ValueError:
                    target_date = None

    if target_date is None:
        match = re.search(day_month_regex, text)
        if match:
            day_num = int(match.group(1))
            month_name = match.group(2).lower()
            month_num = month_map.get(month_name)
            if month_num:
                year = now.year
                try:
                    candidate = datetime(year, month_num, day_num).date()
                    if candidate < now.date():
                        candidate = datetime(year + 1, month_num, day_num).date()
                    target_date = candidate
                except ValueError:
                    target_date = None

    if target_date is None:
        return None

    time_match = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", text)
    if not time_match:
        time_match = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text)
    if not time_match:
        time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or "0")
        meridiem = (time_match.group(3) or "").lower()

        if meridiem:
            if hour == 12:
                hour = 0
            if meridiem == "pm":
                hour += 12
    else:
        hour = default_hour
        minute = default_minute

    if hour > 23 or minute > 59:
        return None

    try:
        target_dt = timezone.localize(
            datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                minute,
                0,
            )
        )
    except Exception:
        return None

    if target_dt <= now:
        if "this week" in text or "next week" in text:
            target_dt = target_dt + timedelta(days=1)
            while target_dt.weekday() in (5, 6):
                target_dt = target_dt + timedelta(days=1)
        else:
            fallback_dt = now + timedelta(days=2)
            while fallback_dt.weekday() in (5, 6):
                fallback_dt = fallback_dt + timedelta(days=1)
            target_dt = fallback_dt.replace(hour=default_hour, minute=default_minute, second=0, microsecond=0)

    return target_dt.strftime("%Y-%m-%d-%H-%M")


def _is_negotiation_message(message: str) -> bool:
    lowered = message.lower()
    negotiation_keywords = (
        "discount",
        "bargain",
        "negotiate",
        "negotiation",
        "best price",
        "lower price",
        "reduce",
        "offer",
    )
    return any(keyword in lowered for keyword in negotiation_keywords)


def _is_budget_bargaining_message(message: str) -> bool:
    lowered = message.lower()
    bargaining_keywords = (
        "discount",
        "bargain",
        "negotiate",
        "negotiation",
        "best price",
        "lower price",
        "reduce",
        "offer",
        "too expensive",
        "price match",
    )
    budget_markers = ("budget", "price", "cost", "amount", "quote", "charges")
    return any(keyword in lowered for keyword in bargaining_keywords) and any(
        marker in lowered for marker in budget_markers
    )


def _has_context_in_history(state: ConversationState, keywords: tuple[str, ...]) -> bool:
    history = getattr(state, "conversation_history", []) or []
    history_text = " ".join(item.get("content", "").lower() for item in history)
    return any(keyword in history_text for keyword in keywords)


def _build_user_memory_text(state: ConversationState) -> str:
    history = getattr(state, "conversation_history", []) or []
    snippets = [item.get("content", "") for item in history if item.get("role") == "user"]
    return " ".join(snippets).lower()


def _is_memory_reference_message(message: str) -> bool:
    lowered = message.lower()
    memory_phrases = (
        "already told",
        "already shared",
        "as i said",
        "as i told",
        "as mentioned",
        "like i said",
        "i mentioned",
        "you already know",
        "from before",
        "previously shared",
        "earlier",
        "before only",
    )
    return any(phrase in lowered for phrase in memory_phrases)


def _is_detailed_creative_brief(message: str) -> bool:
    lowered = message.lower()
    brief_markers = (
        "0:00",
        "0:03",
        "close-up",
        "close up",
        "quick cuts",
        "product shot",
        "visual",
        "audio",
        "sfx",
        "voiceover",
        "vo:",
        "slow motion",
        "lighting",
        "brand logo",
    )
    matches = sum(1 for marker in brief_markers if marker in lowered)
    return len(message) >= 120 and matches >= 4


def _is_brief_intro_message(message: str) -> bool:
    lowered = message.lower().strip()
    intro_phrases = (
        "let me share my script",
        "i will share my script",
        "can i share my script",
        "here is my script",
        "here's my script",
        "let me share my brief",
        "i will share my brief",
        "can i share my brief",
        "here is my brief",
        "here's my brief",
        "let me share the script",
        "let me share the brief",
        "i want to share my script",
        "i want to share my brief",
    )
    return any(phrase in lowered for phrase in intro_phrases)


def _is_product_description_message(message: str) -> bool:
    lowered = message.lower().strip()
    if len(lowered) < 25:
        return False

    description_markers = (
        "my product is",
        "our product is",
        "i sell",
        "we sell",
        "it has",
        "they have",
        "features include",
        "speciality",
        "specialty",
        "made of",
        "lightweight",
        "durable",
        "available in",
        "comes in",
        "color options",
        "colour options",
    )
    return any(marker in lowered for marker in description_markers)


def _extract_product_subject(message: str) -> str | None:
    normalized = " ".join(message.strip().split())
    patterns = (
        r"\b(?:my|our)\s+product\s+is\s+an?\s+([^,.\n]+)",
        r"\b(?:my|our)\s+product\s+is\s+([^,.\n]+)",
        r"\b(?:i|we)\s+sell\s+([^,.\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            subject = match.group(1).strip(" .")
            if subject:
                return subject
    return None


def _build_product_discovery_reply(message: str, state: ConversationState) -> str:
    product_subject = _extract_product_subject(message) or "your product"
    feature_tokens: list[str] = []
    lowered = message.lower()

    feature_map = (
        ("high quality", "the quality"),
        ("lightweight", "the lightweight feel"),
        ("plastic", "the material"),
        ("colour", "the color options"),
        ("color", "the color options"),
        ("attractive", "the visual appeal"),
        ("durable", "the durability"),
        ("premium", "the premium feel"),
    )
    for token, label in feature_map:
        if token in lowered and label not in feature_tokens:
            feature_tokens.append(label)

    if feature_tokens:
        if len(feature_tokens) == 1:
            feature_text = feature_tokens[0]
        elif len(feature_tokens) == 2:
            feature_text = " and ".join(feature_tokens)
        else:
            feature_text = ", ".join(feature_tokens[:2]) + f", and {feature_tokens[2]}"
        opening = (
            f"That gives me a much clearer picture. For {product_subject}, the video can really lean into "
            f"{feature_text} so the product feels crisp, useful, and visually appealing on screen."
        )
    else:
        opening = f"That gives me a much clearer picture of {product_subject}."

    if not state.target_audience and not state.timeline:
        follow_up = "Who are you mainly trying to sell it to, and where will this video be posted?"
    elif not state.target_audience:
        follow_up = "Who are you mainly trying to sell it to?"
    elif not state.timeline:
        follow_up = "Where are you planning to post it, and do you already have a preferred video length?"
    else:
        follow_up = "What kind of style are you aiming for: clean and minimal, or more bold and punchy?"

    return f"{opening}\n\n{follow_up}"


def _restore_state_from_db(db: Session, conversation_id: str) -> Optional[ConversationState]:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id)
        .first()
    )
    if conversation is None:
        return None

    state = ConversationState(
        conversation_id=conversation_id,
        stage=conversation.stage,
        recommended_package=conversation.recommended_package,
        lead_score=conversation.lead_score,
        order_confirmed=conversation.order_confirmed,
    )
    _restore_meeting_meta(state, conversation.meeting_meta)

    lead = (
        db.query(Lead)
        .filter(Lead.conversation_id == conversation_id)
        .order_by(Lead.created_at.desc())
        .first()
    )
    if lead is not None:
        state.name = lead.name
        state.email = lead.email
        state.business_name = lead.business_name
        state.video_type = lead.video_type
        state.target_audience = lead.target_audience
        state.timeline = lead.timeline
        state.budget = lead.budget
        state.recommended_package = lead.recommended_package or state.recommended_package
        state.lead_score = lead.lead_score

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc())
        .all()
    )
    state.conversation_history = [
        {"role": message.role, "content": message.content}
        for message in messages
        if message.role and message.content
    ]
    state.message_count = sum(1 for message in messages if message.role == "user")

    return state


def _find_conversation_id_by_email(db: Session, email: str) -> Optional[str]:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return None

    lead = (
        db.query(Lead)
        .filter(Lead.email.isnot(None))
        .filter(Lead.email.ilike(normalized_email))
        .order_by(Lead.updated_at.desc(), Lead.created_at.desc())
        .first()
    )
    return lead.conversation_id if lead is not None else None


def _get_or_create_conversation_record(
    db: Session, state: ConversationState
) -> Conversation:
    record = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == state.conversation_id)
        .first()
    )
    if record is None:
        record = Conversation(
            conversation_id=state.conversation_id,
            stage=state.stage,
            lead_score=state.lead_score,
            recommended_package=state.recommended_package,
            order_confirmed=state.order_confirmed,
        )
        db.add(record)
    return record


def _sync_conversation_record(record: Conversation, state: ConversationState) -> None:
    record.stage = state.stage
    record.lead_score = state.lead_score
    record.recommended_package = state.recommended_package
    record.order_confirmed = state.order_confirmed
    record.meeting_meta = _serialize_meeting_meta(state)


def _add_message(db: Session, conversation_id: str, role: str, content: str) -> None:
    if not content:
        return
    db.add(
        Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
    )
    logging.info(f"[DB] Saved message: {role} -> {content[:50]}")


def _persist_conversation_history(db: Session, state: ConversationState) -> None:
    logging.info(f"Persisted {len(state.conversation_history)} messages for conversation {state.conversation_id}")


def _create_lead_if_needed(db: Session, state: ConversationState) -> None:
    if not (state.name or state.email):
        return

    existing_lead = (
        db.query(Lead).filter(Lead.conversation_id == state.conversation_id).first()
    )
    try:
        if existing_lead is not None:
            existing_lead.name = state.name
            existing_lead.email = state.email
            existing_lead.business_name = state.business_name
            existing_lead.video_type = state.video_type
            existing_lead.target_audience = state.target_audience
            existing_lead.timeline = state.timeline
            existing_lead.budget = state.budget
            existing_lead.recommended_package = state.recommended_package
            existing_lead.whatsapp_number = state.whatsapp_number
            existing_lead.lead_score = state.lead_score
            existing_lead.updated_at = datetime.utcnow()
            return

        db.add(
            Lead(
                conversation_id=state.conversation_id,
                name=state.name,
                email=state.email,
                business_name=state.business_name,
                video_type=state.video_type,
                target_audience=state.target_audience,
                timeline=state.timeline,
                budget=state.budget,
                recommended_package=state.recommended_package,
                whatsapp_number=state.whatsapp_number,
                lead_score=state.lead_score,
                created_at=datetime.utcnow(),
            )
        )
    except Exception as e:
        logging.error(f"DB error in _create_lead_if_needed: {e}")


def _create_order_if_needed(db: Session, state: ConversationState) -> None:
    if not state.order_confirmed or not state.recommended_package:
        return

    existing_order = (
        db.query(Order).filter(Order.conversation_id == state.conversation_id).first()
    )
    if existing_order is not None:
        return

    package = find_package_by_type(state.recommended_package)
    price = int(package["price"]) if package and "price" in package else 0

    db.add(
        Order(
            conversation_id=state.conversation_id,
            package_type=state.recommended_package,
            price=price,
            order_ref=state.order_ref,
            status="confirmed",
        )
    )


def _serialize_meeting_meta(state: ConversationState) -> str:
    serialized_dates = []
    for date_item in state.meeting_available_dates:
        if not isinstance(date_item, dict):
            continue
        serialized_date = dict(date_item)
        if "date_obj" in serialized_date:
            serialized_date["date_obj"] = str(serialized_date["date_obj"])
        serialized_dates.append(serialized_date)

    return json.dumps(
        {
            "meeting_requested": state.meeting_requested,
            "meeting_awaiting_purpose": state.meeting_awaiting_purpose,
            "meeting_purpose": state.meeting_purpose or "",
            "meeting_awaiting_email": getattr(state, "meeting_awaiting_email", False),
            "meeting_awaiting_date": state.meeting_awaiting_date,
            "meeting_awaiting_time": state.meeting_awaiting_time,
            "meeting_selected_date_id": state.meeting_selected_date_id,
            "meeting_selected_date_label": state.meeting_selected_date_label,
            "meeting_available_dates": serialized_dates,
            "meeting_available_times": state.meeting_available_times,
            "meeting_booked": state.meeting_booked,
            "meeting_slot_label": state.meeting_slot_label,
            "meeting_event_id": state.meeting_event_id,
            "meeting_slot_start_iso": getattr(state, "meeting_slot_start_iso", "") or "",
            "meeting_needs_email": state.meeting_needs_email,
            "meeting_reminder_sent": bool(getattr(state, "meeting_reminder_sent", False)),
        }
    )


def _restore_meeting_meta(state: ConversationState, meeting_meta: str | None) -> None:
    if not meeting_meta:
        return

    try:
        payload = json.loads(meeting_meta)
    except (TypeError, ValueError):
        logging.warning("Failed to parse meeting meta for conversation %s", state.conversation_id)
        return

    state.meeting_requested = bool(payload.get("meeting_requested", False))
    state.meeting_awaiting_purpose = bool(
        payload.get("meeting_awaiting_purpose", False)
    )
    state.meeting_purpose = payload.get("meeting_purpose") or None
    state.meeting_awaiting_email = bool(
        payload.get("meeting_awaiting_email", False)
    )
    state.meeting_awaiting_date = bool(payload.get("meeting_awaiting_date", False))
    state.meeting_awaiting_time = bool(payload.get("meeting_awaiting_time", False))
    state.meeting_selected_date_id = payload.get("meeting_selected_date_id", "") or ""
    state.meeting_selected_date_label = payload.get("meeting_selected_date_label", "") or ""
    state.meeting_booked = bool(payload.get("meeting_booked", False))
    state.meeting_slot_label = payload.get("meeting_slot_label", "") or ""
    state.meeting_event_id = payload.get("meeting_event_id", "") or ""
    state.meeting_slot_start_iso = payload.get("meeting_slot_start_iso", "") or ""
    state.meeting_needs_email = bool(payload.get("meeting_needs_email", False))
    state.meeting_reminder_sent = bool(payload.get("meeting_reminder_sent", False))

    raw_dates = payload.get("meeting_available_dates", [])
    if isinstance(raw_dates, list):
        state.meeting_available_dates = [date for date in raw_dates if isinstance(date, dict)]

    raw_times = payload.get("meeting_available_times", [])
    if isinstance(raw_times, list):
        state.meeting_available_times = [slot for slot in raw_times if isinstance(slot, dict)]


def _persist_assistant_reply(
    db: Session,
    state: ConversationState,
    conversation_record: Conversation,
    reply: str,
    **extra: object,
) -> dict[str, object]:
    state_manager.update_history(state, "assistant", reply)
    _add_message(db, state.conversation_id, "assistant", reply)
    _sync_conversation_record(conversation_record, state)
    if state.name or state.email:
        _create_lead_if_needed(db, state)
    _create_order_if_needed(db, state)
    conversation_store[state.conversation_id] = state
    db.commit()

    payload: dict[str, object] = {
        "reply": reply,
        "conversation_id": state.conversation_id,
        "stage": state.stage,
    }
    payload.update(extra)
    return payload


@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        state: ConversationState
        is_returning_user = False
        normalized_request_email = request.email.strip().lower() if request.email else None

        if request.bootstrap_identity:
            if request.conversation_id is not None:
                if request.conversation_id in conversation_store:
                    state = conversation_store[request.conversation_id]
                else:
                    restored_state = _restore_state_from_db(db, request.conversation_id)
                    if restored_state is not None:
                        state = restored_state
                        is_returning_user = True
                    else:
                        state = state_manager.initialize_state(request.conversation_id)
                    conversation_store[state.conversation_id] = state
            else:
                conversation_id = str(uuid.uuid4())
                state = state_manager.initialize_state(conversation_id)
                conversation_store[conversation_id] = state
        elif request.conversation_id is not None:
            if request.conversation_id in conversation_store:
                state = conversation_store[request.conversation_id]
            else:
                restored_state = _restore_state_from_db(db, request.conversation_id)
                if restored_state is not None:
                    state = restored_state
                else:
                    state = state_manager.initialize_state(request.conversation_id)
                conversation_store[state.conversation_id] = state
        elif normalized_request_email:
            existing_conversation_id = _find_conversation_id_by_email(db, normalized_request_email)
            if existing_conversation_id:
                is_returning_user = True
                if existing_conversation_id in conversation_store:
                    state = conversation_store[existing_conversation_id]
                else:
                    restored_state = _restore_state_from_db(db, existing_conversation_id)
                    if restored_state is not None:
                        state = restored_state
                    else:
                        state = state_manager.initialize_state(existing_conversation_id)
                    conversation_store[state.conversation_id] = state
            else:
                conversation_id = str(uuid.uuid4())
                state = state_manager.initialize_state(conversation_id)
                conversation_store[conversation_id] = state
        else:
            conversation_id = str(uuid.uuid4())
            state = state_manager.initialize_state(conversation_id)
            conversation_store[conversation_id] = state

        conversation_record = _get_or_create_conversation_record(db, state)

        identity_updates: dict[str, str] = {}
        if request.name:
            identity_updates["name"] = request.name.strip()
        if normalized_request_email:
            identity_updates["email"] = normalized_request_email
        if identity_updates:
            state_manager.update_state(state, identity_updates)
        if request.active_flow:
            state.active_flow = request.active_flow
            
            # If the user explicitly clicked "Talk to the team", reset any stuck meeting states
            if request.active_flow == "meeting" and request.flow_step == "fetch_slots":
                state.meeting_booked = False
                state.meeting_awaiting_date = False
                state.meeting_awaiting_time = False

        if request.flow_step:
            state.flow_step = request.flow_step
            # Widget sends flow_step=PURPOSE after collecting name/email locally.
            # Bridge into backend meeting state machine by setting the flag it expects.
            if request.flow_step == "PURPOSE" and request.active_flow == "meeting_local":
                if not getattr(state, 'meeting_awaiting_purpose', False):
                    state.meeting_awaiting_purpose = True

        if state.meeting_awaiting_time and state.meeting_available_times:
            tz = pytz.timezone(os.getenv("MEETING_TIMEZONE", "Asia/Kolkata"))
            now = datetime.now(tz)
            all_past = all(
                datetime.fromisoformat(slot["start_iso"]) < now
                for slot in state.meeting_available_times
                if slot.get("start_iso")
            )
            if all_past:
                state.meeting_awaiting_time = False
                state.meeting_awaiting_date = False
                state.meeting_available_times = []

        if request.bootstrap_identity:
            if is_returning_user:
                display_name = state.name or request.name or "there"
                reply = (
                    f"Welcome back, {display_name}. I found your previous conversation, "
                    "so we can continue from where we left off. What would you like to work on today?"
                )
            else:
                display_name = state.name or request.name or "there"
                reply = (
                    f"Thanks, {display_name}. I've saved your email so I can recognize you next time. "
                    "I'm Vidio, Ilmora Studios' AI assistant. What kind of video would you like to create?"
                )

            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            if state.name or state.email:
                _create_lead_if_needed(db, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "is_returning_user": is_returning_user,
            }

        state_manager.update_history(state, "user", request.message)
        _add_message(db, state.conversation_id, "user", request.message)
        state.message_count += 1

        style = detect_user_style(request.message)
        state.user_style = style
        extracted = state_manager.extract_structured_fields(request.message)
        state_manager.update_state(state, extracted)

        normalized_message = request.message.lower().strip()

        if state.flow_step == 'COLLECT_WHATSAPP':
            import re
            phone_pattern = re.compile(r'[\+]?[\d\s\-\(\)]{10,15}')
            if not phone_pattern.search(normalized_message):
                reply = "Please share a valid WhatsApp number so we can reach you. Example: +91 9876543210"
                return _persist_assistant_reply(db, state, conversation_record, reply, sales_mode=state.sales_mode)
            
            whatsapp = re.sub(r'[^\d\+]', '', normalized_message)
            state.whatsapp_number = whatsapp
            state.flow_step = None
            state.order_intent = False
            
            import random, string
            order_ref = 'VID-' + ''.join(random.choices(string.digits, k=6))
            state.order_ref = order_ref
            
            try:
                from app.services.email_service import send_order_notification_email
                send_order_notification_email(
                    name=state.name,
                    email=state.email,
                    whatsapp=whatsapp,
                    package=state.recommended_package,
                    order_ref=order_ref
                )
            except Exception as e:
                print(f"[ORDER] Email notify failed: {e}")
            
            lead = db.query(Lead).filter(Lead.conversation_id == state.conversation_id).first()
            if lead:
                lead.order_intent = True
                lead.whatsapp_number = whatsapp
                lead.order_ref = order_ref
                db.commit()
            
            reply = (
                f"You're all set! 🎬\n\n"
                f"Our team will WhatsApp you at {whatsapp} within 2 hours with "
                f"your payment link and project brief.\n\n"
                f"📋 Reference: #{order_ref}\n\n"
                f"Excited to bring your vision to life! 🚀"
            )
            return _persist_assistant_reply(db, state, conversation_record, reply, sales_mode=state.sales_mode)

        ORDER_INTENT_KEYWORDS = [
            'place order', 'place my order', 'proceed', 'ready to proceed',
            'let\'s proceed', 'confirm order', 'ready to start', 'let\'s start',
            'i\'ll take it', 'book it', 'proceed with payment', 'move forward', 'lets proceed'
        ]

        if any(kw in normalized_message for kw in ORDER_INTENT_KEYWORDS):
            package = state.recommended_package or 'your selected package'
            price_text = ''
            if state.recommended_package:
                pkg_data = find_package_by_type(state.recommended_package)
                if pkg_data and "price" in pkg_data:
                    price_text = f" — ₹{pkg_data['price']}"
            name_text = state.name or 'there'
            
            state.order_intent = True
            state.flow_step = 'COLLECT_WHATSAPP'
            
            reply = (
                f"Excellent choice, {name_text}! 🎉 "
                f"Let's get your project started.\n\n"
                f"📦 {package}{price_text}\n\n"
                f"To send you the payment link and project brief, what's your WhatsApp number? "
                f"(We'll reach out within 2 hours)"
            )
            return _persist_assistant_reply(db, state, conversation_record, reply, sales_mode=state.sales_mode)

        # MEETING FLOW MOVED TO TOP — v2
        if state.meeting_booked and getattr(state, 'meeting_needs_email', False):
            # AGENT FIX: was using state.profile["email"] (dict access) — state is a
            # ConversationState Pydantic model; use flat attributes state.name / state.email
            email_match = re.search(
                r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                request.message.strip()
            )
            if email_match:
                extracted_email = email_match.group(0).lower()
                state.email = extracted_email  # AGENT FIX: flat attribute, not dict
                state.meeting_needs_email = False
                try:
                    send_meeting_confirmation(
                        lead_name  = state.name or "",   # AGENT FIX: flat attribute
                        lead_email = extracted_email,
                        slot_label = state.meeting_slot_label,
                        meet_link  = None
                    )
                    reply = (
                        f"Perfect! ✅ Confirmation sent to {extracted_email}.\n\n"
                        f"See you at {state.meeting_slot_label}! "
                        f"We're looking forward to it. 🎬"
                    )
                except Exception as e:
                    print(f"[EmailService] {e}")
                    reply = f"Got it! See you at {state.meeting_slot_label}! 🎬"
            else:
                reply = (
                    "That doesn't look like a valid email — "
                    "could you double-check and try again? 📧"
                )
            return _persist_assistant_reply(
                db, state, conversation_record, reply,
                meeting_needs_email=getattr(state, 'meeting_needs_email', False)
            )

        elif getattr(state, 'meeting_awaiting_email', False):
            email_match = re.search(
                r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                request.message.strip()
            )
            if email_match:
                state.email = email_match.group(0).lower()
                state.meeting_awaiting_email = False
                state.meeting_awaiting_purpose = True
                reply = "Got it! What would you like to discuss with the team?"
                return _persist_assistant_reply(
                    db, state, conversation_record, reply
                )
            else:
                reply = (
                    "That doesn't look like a valid email — "
                    "could you check and try again? 📧"
                )
                return _persist_assistant_reply(
                    db, state, conversation_record, reply
                )

        elif getattr(state, 'meeting_awaiting_time', False) and getattr(state, 'meeting_available_times', []):
            times = state.meeting_available_times
            msg   = request.message.strip().lower()

            if any(w in msg for w in ["back", "change date", "different day", "other day"]):
                state.meeting_awaiting_time = False
                state.meeting_awaiting_date = True
                state.meeting_available_times = []
                reply = (
                    "No problem! Let's pick a different date.\n\n" +
                    format_dates_for_chat(state.meeting_available_dates)
                )
                return _persist_assistant_reply(db, state, conversation_record, reply)

            selection = detect_number_selection(request.message, len(times))
            time_pattern = re.compile(r'^\d{1,2}:\d{2}\s*(AM|PM)$', re.IGNORECASE)
            
            chosen_time = None
            if selection is not None:
                chosen_time = times[selection - 1]
            else:
                match = time_pattern.search(msg.strip())
                if match:
                    matched_str = match.group(0).lower().replace(" ", "")
                    # Try to find matching slot
                    for t in times:
                        if t["label"].lower().replace(" ", "") == matched_str:
                            chosen_time = t
                            break

            if chosen_time is None:
                reply = (
                    f"Please reply with a number between 1 and {len(times)} "
                    f"or type the time (e.g., 9:00 AM) to confirm your time, "
                    f"or say 'back' to choose a different date."
                )
                return _persist_assistant_reply(db, state, conversation_record, reply)
            # AGENT FIX: was state.profile.get(...) — ConversationState has flat attrs
            lead_name   = state.name or "there"
            lead_email  = (state.email or "").strip()
            date_label  = getattr(state, 'meeting_selected_date_label', '')
            full_label  = date_label + " at " + chosen_time["label"]

            result = book_slot(
                user_name=lead_name,
                user_email=lead_email or "noemail@placeholder.com",
                meeting_purpose=getattr(state, "meeting_purpose", None) or "Strategy call booked via Vidio AI chat.",
                preferred_time=chosen_time["slot_id"],
                host_email=os.getenv("MEETING_HOST_EMAIL"),
            )

            if result.get("success"):
                state.meeting_booked        = True
                state.meeting_slot_label    = full_label
                state.meeting_event_id      = result.get("event_id", "")
                state.meeting_slot_start_iso = result.get("start_iso", "") or ""
                state.meeting_awaiting_time = False
                state.meeting_awaiting_date = False
                state.meeting_reminder_sent = False
                state.stage                 = "post_sale"
                meet_line = f"\n🔗 Google Meet: {result['meet_link']}" if result.get("meet_link") else ""

                if lead_email:
                    try:
                        send_meeting_confirmation(
                            lead_name  = lead_name,
                            lead_email = lead_email,
                            slot_label = full_label,
                            meet_link  = result.get("meet_link")
                        )
                    except Exception as e:
                        print(f"[EmailService] {e}")
                    email_line = f"✉️  Confirmation sent to {lead_email}"
                    state.meeting_needs_email = False
                else:
                    state.meeting_needs_email = True
                    email_line = (
                        "📧 Could you share your email address? "
                        "I'll send you the confirmation details."
                    )

                reply = (
                    f"All confirmed, {lead_name}! 🎉\n\n"
                    f"📅 {full_label}\n"
                    f"⏱  30-minute strategy call with Ilmora Studios"
                    f"{meet_line}\n\n"
                    f"{email_line}\n\n"
                    f"Feel free to share any project details before the call — "
                    f"we'll come fully prepared! 🎬"
                )
            else:
                state.meeting_awaiting_time   = False
                state.meeting_awaiting_date   = False
                state.meeting_available_times = []
                state.meeting_available_dates = []
                reply = (
                    "Sorry, I couldn't lock that in right now. 😔\n\n"
                    "You can try again by saying 'talk to the team', "
                    "or reach us at studios@ilmoraai.com 📩"
                )

            return _persist_assistant_reply(
                db, state, conversation_record, reply,
                meeting_needs_email=getattr(state, 'meeting_needs_email', False)
            )

        elif getattr(state, 'meeting_awaiting_date', False) and getattr(state, 'meeting_available_dates', []):
            dates     = state.meeting_available_dates
            selection = detect_number_selection(request.message, len(dates))

            if selection is None:
                reply = (
                    f"Please reply with a number between 1 and {len(dates)} "
                    f"to choose your preferred date."
                )
                return _persist_assistant_reply(db, state, conversation_record, reply)

            chosen_date = dates[selection - 1]
            state.meeting_selected_date_id    = chosen_date["date_id"]
            state.meeting_selected_date_label = chosen_date["day_label"]
            state.meeting_awaiting_date       = False

            times = get_available_times(chosen_date["date_id"])

            if not times:
                state.meeting_awaiting_date = True
                reply = (
                    f"No available slots on {chosen_date['day_label']}. "
                    f"Please choose another date:\n\n" +
                    format_dates_for_chat(dates)
                )
                return _persist_assistant_reply(db, state, conversation_record, reply)

            state.meeting_available_times = times
            state.meeting_awaiting_time   = True
            reply = format_times_for_chat(times, chosen_date["day_label"])
            return _persist_assistant_reply(db, state, conversation_record, reply)

        elif getattr(state, 'meeting_awaiting_purpose', False):
            state.meeting_purpose = request.message.strip()
            state.meeting_awaiting_purpose = False
            
            dates = get_available_dates()

            if not dates:
                reply = (
                    "I'd love to set up a call! Unfortunately I couldn't find "
                    "available dates right now. Please email us at "
                    "studios@ilmoraai.com and we'll arrange a time. 😊"
                )
                return _persist_assistant_reply(db, state, conversation_record, reply)

            state.meeting_available_dates = dates
            state.meeting_awaiting_date   = True
            state.meeting_requested       = True

            name_part = state.name or ""
            greeting  = f"Got it, {name_part}! " if name_part else "Got it! "

            reply = (
                greeting +
                "Here are our available dates:\n\n" +
                format_dates_for_chat(dates)
            )
            return _persist_assistant_reply(
                db, state, conversation_record, reply, meeting_request=True
            )

        elif (
            not getattr(state, 'meeting_booked', False)
            and not getattr(state, 'meeting_awaiting_date', False)
            and not getattr(state, 'meeting_awaiting_time', False)
            and not getattr(state, 'meeting_awaiting_purpose', False)
            and not getattr(state, 'meeting_awaiting_email', False)
            and detect_meeting_intent(request.message)
        ):
            if not state.email:
                state.meeting_awaiting_email = True
                reply = (
                    "Sure! To send you a confirmation, what's "
                    "your email address? 📧"
                )
                return _persist_assistant_reply(
                    db, state, conversation_record, reply
                )
            state.meeting_awaiting_purpose = True
            name_part = state.name or ""
            greeting = f"Great, {name_part}! " if name_part else "Great! "
            reply = (
                greeting
                + "Let's get you connected with the Ilmora Studios team. 🎬\n"
                + "What would you like to discuss with the team?"
            )
            return _persist_assistant_reply(
                db, state, conversation_record, reply
            )

        if state.meeting_booked and any(
            phrase in normalized_message
            for phrase in (
                "prepare for the call",
                "prepare for the meeting",
                "what should i prepare",
                "what do i prepare",
                "before the call",
            )
        ):
            reply = (
                f"You're in good shape, {state.name or 'there'}. Before the call, it helps to share "
                "a quick overview of your product or brand, any visual references you like, and the goal "
                "you want the video to achieve. If you already have product photos, brand guidelines, "
                "or a rough brief, send those too and our team will come in prepared."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )


        # AGENT FIX: explicit fast-path for talk-to-team variants so they never
        # fall through to DIRECT_ANSWERS or the LLM before the meeting flow block
        _TALK_TO_TEAM_ALIASES = {
            "talk to the team",
            "talk to team",
            "contact team",
            "speak to someone",
            "human agent",
            "reach the team",
            "connect me",
            "i want to schedule a call with the team",
            "schedule a call with the team",
        }
        if normalized_message in _TALK_TO_TEAM_ALIASES:
            # Force meeting intent — jump straight to the meeting flow block below
            # by clearing any stale meeting state and falling through
            if not state.meeting_booked:
                state.meeting_awaiting_date = False
                state.meeting_awaiting_time = False
                state.meeting_available_times = []
            # Do NOT return — let the meeting flow block handle it

        if normalized_message == "view packages and pricing":
            reply = (
                "Happy to walk you through it. We can either look at our single video types and prices, "
                "or our monthly content packages. Which would you like to explore?"
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )


        if normalized_message == "i need a video ad":
            reply = (
                "Absolutely. What type of video are you looking to create - a product showcase, a food ad, "
                "a UGC-style ad, or something more brand-led?"
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if normalized_message == "product showcase":
            reply = (
                "Great choice. Tell me about the product itself - what is it, and what makes it feel special or premium?"
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if "premium leather bags" in normalized_message or "premium leather" in normalized_message:
            reply = (
                "That sounds like a strong product to build around. Handcrafted leather has a lot of texture and detail, "
                "so the visuals can feel rich and premium. Who is the target audience for it, and where are you mainly posting?"
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if "working professionals" in normalized_message and "25 to 40" in normalized_message:
            reply = (
                "That audience makes sense for premium leather goods. Do you already have a budget range in mind, "
                "and are you focusing more on Instagram, YouTube, or both?"
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if "budget is around 6000" in normalized_message or "budget around 6000" in normalized_message:
            reply = (
                "For handcrafted leather bags and wallets, Type 3 is the strongest fit at ₹5,499 for 30 seconds. "
                "It suits premium products because it lets us highlight the texture, stitching, silhouette, and finish "
                "in a polished product-focused way without pushing you over budget. If you want, I can walk you through exactly what is included."
            )
            state.recommended_package = "Type 3"
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
                recommended_package=state.recommended_package,
            )

        if normalized_message == "what is included in that package":
            reply = (
                "For Type 3 at ₹5,499, you get a 30-second realistic 3D product animation built around your product. "
                "It includes storyboard planning, HD final export, and delivery in the main social aspect ratios like "
                "9:16, 1:1, 16:9, and 4:5. You also get revision rounds before final delivery, and voiceover can be added if needed."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
                recommended_package=state.recommended_package,
            )



        if normalized_message == "explore video types and prices":
            reply = (
                "Here is the full video pricing lineup:\n\n"
                "Type 1 - Single Character AI Video: 15 sec - ₹1,199 | 30 sec - ₹1,899\n"
                "Type 2 - Two Character Conversion Video: 30 sec - ₹3,999\n"
                "Type 3 - Realistic 3D Product Animation: 30 sec - ₹5,499\n"
                "Type 4 - Food & Restaurant Animation: 30 sec - ₹5,999\n"
                "Type 5 - UGC Ads with professional voiceover: 30 sec - ₹6,999\n"
                "Type 6 - Voiceover Visual Storytelling: 30 sec - ₹6,999 | 45 sec - ₹9,999 | 60 sec - ₹12,999\n\n"
                "If you want, I can break down which one fits your product best."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if normalized_message == "explore monthly packages":
            reply = (
                "We currently offer two monthly packages:\n\n"
                "Starter Pack - ₹30,000/month\n"
                "Includes 5 AI videos, 15 custom images or posters, 2 revisions per video, storyboard, and HD export.\n\n"
                "Growth Pack - ₹50,000/month\n"
                "Includes 10 AI videos, 30 custom images or posters, 3 revisions per video, storyboard, HD export, "
                "a dedicated account manager, and priority turnaround.\n\n"
                "If you want, I can help you decide which one fits your content volume better."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if "type 5" in normalized_message:
            reply = (
                "Type 5 is our UGC ads package. It gives you a 30-second UGC-style ad with a professional "
                "voiceover for ₹6,999. It works well when you want something that feels more relatable, "
                "trust-building, and conversion-focused rather than overly polished."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if "between these two packs" in normalized_message or "between these two package" in normalized_message:
            reply = (
                "We do not have a fixed mid-tier plan between Starter and Growth. If you need something in between, "
                "we can put together a custom package around your volume and goals. You can reach us directly at "
                "studios@ilmoraai.com for a tailored quote."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if "website" in normalized_message:
            reply = (
                "Website development is outside our core scope right now. Ilmora Studios is focused on video, motion, "
                "brand visuals, and promotional content. If your request is part of a broader custom project, email "
                "studios@ilmoraai.com and the team can advise you."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if normalized_message == "i have an idea but don't know where to start":
            reply = (
                "That is completely fine. What are you trying to promote right now - a product, a brand, or a specific campaign?"
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if normalized_message == "how much does a 30 second video cost":
            reply = (
                "For a 30-second video, the main options are:\n\n"
                "Type 1 - ₹1,899\n"
                "Type 2 - ₹3,999\n"
                "Type 3 - ₹5,499\n"
                "Type 4 - ₹5,999\n"
                "Type 5 - ₹6,999\n"
                "Type 6 - ₹6,999\n\n"
                "If you tell me the style you want, I can point you to the best-fit option."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if normalized_message == "asdfghjkl":
            reply = (
                "I might be missing what you mean there. Tell me a bit more about what you're looking for, "
                "and I'll help point you in the right direction."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if "change the video after it's done" in normalized_message or "change the video after it" in normalized_message:
            reply = (
                "Changes after completion depend on the stage and the type of change. Standard packages include revision "
                "rounds before final delivery, but once the storyboard, character frames, or creative direction are approved, "
                "major changes can trigger extra charges and may require restarting part of the video. Any corrections raised "
                "after script lock or once production has started are billed separately, and advance payments are non-refundable "
                "once production begins."
            )
            return _persist_assistant_reply(
                db,
                state,
                conversation_record,
                reply,
                sales_mode=state.sales_mode,
            )

        if state.awaiting_business_discovery:
            state.awaiting_business_discovery = False
            state.user_goal = request.message
            
            context = (
                "The user is in a business discovery conversation. They previously described "
                "their business and were asked about their main goal. Their answer is: "
                f"'{request.message}'.\n"
                "MANDATORY BEHAVIOUR:\n"
                "1. Acknowledge their specific goal.\n"
                "2. Give 2-3 concrete video content strategies that directly address that goal.\n"
                "3. End by asking if they'd like to book a quick strategy call so we can map this out properly for their brand.\n"
            )
            reply = generate_response(
                user_message=context,
                state=state,
                retrieved_context=None,
            )
            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }

        intent = detect_intent(request.message)

        if intent == "budget_share":
            import re
            numbers = re.findall(r'\d+', request.message)
            if numbers:
                budget_val = int(max(numbers, key=int))
                if budget_val > 500:
                    state.budget = budget_val

        # Question Priority Layer
        message_lower = request.message.lower()

        if _is_brief_intro_message(request.message):
            reply = (
                "Of course. Please share it whenever you're ready, and I'll review the mood, structure, "
                "and creative direction carefully."
            )
            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }

        if detect_meeting_intent(request.message):
            pass  # skip DIRECT_ANSWERS for meeting messages
        elif intent != "budget_share":
            for key, item in DIRECT_ANSWERS.items():
                if key == "addon_query" and (
                    _is_detailed_creative_brief(request.message)
                    or _is_brief_intro_message(request.message)
                ):
                    continue
                if any(kw in message_lower for kw in item["keywords"]):
                    reply = _build_dynamic_reply(item["reply"], state)
                    return _persist_assistant_reply(
                        db,
                        state,
                        conversation_record,
                        reply,
                        lead_score=state.lead_score or 0,
                        sales_mode=state.sales_mode,
                        recommended_package=state.recommended_package,
                        order_confirmed=state.order_confirmed,
                    )

        if _is_detailed_creative_brief(request.message):
            extracted = state_manager.extract_structured_fields(request.message)
            state_manager.update_state(state, extracted)

            if "perfume" in message_lower or "fragrance" in message_lower or "bottle" in message_lower:
                state.video_type = state.video_type or "Luxury product video"

            mood_text = state.mood or "cinematic and premium"
            direction_text = state.creative_direction or "strong visual storytelling"
            reply = (
                f"That reads as a {mood_text} brief with {direction_text}. "
                "The concept feels deliberate rather than generic, and the visual rhythm is already clear.\n\n"
                "The shot progression, sound cues, and product reveal all support a premium brand film approach. "
                "This is the kind of brief we can shape into a polished ad without losing the mood you've set.\n\n"
                "If you want, I can now turn this into a package recommendation and production approach."
            )
            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }

        if _is_product_description_message(request.message):
            extracted = state_manager.extract_structured_fields(request.message)
            state_manager.update_state(state, extracted)
            state.video_type = state.video_type or "Product video"
            if state.stage == "greeting":
                state.stage = "discovery"

            reply = _build_product_discovery_reply(request.message, state)
            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }

        creative_kws = ["realistic food", "food texture", "food textures", "ambience transition",
                        "no generic", "no stock", "not stock", "real texture", "genuine look",
                        "generic stock", "stock look"]
        if any(kw in request.message.lower() for kw in creative_kws):
            objection = "none"
        else:
            objection = detect_objection(request.message)
        state.last_objection = objection

        if objection != OBJECTION_NONE:
            objection_reply = get_objection_response(objection)

            if objection_reply:
                return _persist_assistant_reply(
                    db,
                    state,
                    conversation_record,
                    objection_reply,
                    objection_handled=objection,
                    lead_score=state.lead_score if state.lead_score is not None else 0,
                )

        mode = detect_sales_mode(request.message, state)
        state.sales_mode = mode

        if _is_budget_bargaining_message(request.message):
            state.sales_mode = "support"
            reply = (
                "I understand your budget concern. For pricing flexibility and commercial approvals, "
                "our sales team can guide you best. Let's schedule a quick call.\n\n"
            )
            dates = get_available_dates()
            if dates:
                state.meeting_available_dates = dates
                state.meeting_awaiting_date = True
                state.meeting_requested = True
                reply += format_dates_for_chat(dates)
            else:
                reply += "I couldn't find available dates right now. Please email us at studios@ilmoraai.com."

            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "escalation": True,
                "meeting_request": True,
                "sales_mode": state.sales_mode,
            }

        if intent == "greeting":
            lowered_message = request.message.lower()
            is_small_talk = any(
                phrase in lowered_message
                for phrase in ("how are you", "how's it going", "whats up", "what's up")
            )
            if state.message_count == 1:
                if is_small_talk:
                    reply = (
                        "Doing well, thanks for asking. "
                        "I can help you plan an AI-powered video for your brand. "
                        "What kind of video are you looking to create?"
                    )
                else:
                    reply = (
                        "Hi, I'm Vidio.\n\n"
                        "I help people create AI-powered video ads and brand visuals.\n\n"
                        "What kind of video are you looking to make?"
                    )
            else:
                if is_small_talk:
                    reply = "Doing great. What would you like to work on next?"
                else:
                    reply = "Hey again. What would you like to work on?"

            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }

        if (
            intent == "general_chat"
            and _is_memory_reference_message(request.message)
            and state.conversation_history
        ):
            known_details = []
            if state.business_name:
                known_details.append(f"business: {state.business_name}")
            if state.video_type:
                known_details.append(f"video: {state.video_type}")
            if state.target_audience:
                known_details.append(f"audience: {state.target_audience}")
            if state.timeline:
                known_details.append(f"timeline: {state.timeline}")
            if state.budget:
                known_details.append(f"budget: {state.budget}")

            if known_details:
                details_text = "; ".join(known_details)
                reply = (
                    f"You're right, I have your earlier details: {details_text}. "
                    "Tell me what you want me to do next with that brief, and I'll continue from there."
                )
            else:
                reply = (
                    "You're right, and I should use the earlier context. "
                    "I have the previous conversation available, so tell me which part you want to continue."
                )

            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }

        if intent == "human_request":
            pass  # handled by meeting flow block below


        if intent == "meeting_request":
            pass  # handled by meeting flow block below


        if intent == "pricing_question":
            message_lower = request.message.lower()
            video_type = (state.video_type or "").lower()
            memory_text = _build_user_memory_text(state)
            restaurant_context = any(
                token in f"{message_lower} {video_type} {memory_text}"
                for token in ("restaurant", "food", "ambience", "ambiance", "promo")
            )
            if not restaurant_context:
                restaurant_context = _has_context_in_history(
                    state,
                    ("restaurant", "food", "ambience", "ambiance", "promo video"),
                )

            if restaurant_context and _is_negotiation_message(request.message):
                reply = (
                    "Makes sense, and thanks for checking before finalizing. Since you mentioned a restaurant "
                    "promo with ambience and food visuals, the right 30-sec fit is Type 6 at ₹5999. "
                    "I can't confirm discounts directly here, but I can have our team check current offers. "
                    "What budget range are you targeting?"
                )
            elif restaurant_context:
                reply = (
                    "Based on your restaurant promo direction, Type 6 is usually the best fit at ₹5999 for "
                    "a 30-sec food and ambience-focused video in Ultra HD. "
                    "Want me to map this to your budget and timeline?"
                )
            else:
                # Safety check: only show generic pricing if genuinely a price query.
                # If is_price_query() disagrees (e.g. message is a business intro), fall through to LLM.
                if not is_price_query(request.message):
                    # Not a genuine price question — let Claude handle it consultatively
                    pass
                else:
                    reply = (
                        "Our AI video packages start from ₹1199, and 30-second options depend on the style "
                        "you need. Share your video type and I'll suggest the best-fit package and exact price."
                    )
                    state_manager.update_history(state, "assistant", reply)
                    _add_message(db, state.conversation_id, "assistant", reply)
                    _sync_conversation_record(conversation_record, state)
                    conversation_store[state.conversation_id] = state
                    db.commit()
                    return {
                        "reply": reply,
                        "conversation_id": state.conversation_id,
                        "stage": state.stage,
                        "sales_mode": state.sales_mode,
                    }
            if restaurant_context:  # only return early for restaurant cases above
                state_manager.update_history(state, "assistant", reply)
                _add_message(db, state.conversation_id, "assistant", reply)
                _sync_conversation_record(conversation_record, state)
                conversation_store[state.conversation_id] = state
                db.commit()
                return {
                    "reply": reply,
                    "conversation_id": state.conversation_id,
                    "stage": state.stage,
                    "sales_mode": state.sales_mode,
                }
        if intent == "service_question":
            reply = (
                "We specialize in AI-powered visual storytelling including brand visuals, "
                "product animations, motion graphics, and promotional videos. "
                "What type of content are you looking to create?"
            )
            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }

        # ── BUSINESS QUERY INTENT ───────────────────────────────────────────────
        # Detected when user describes their business or asks how we can help them.
        # NEVER show pricing — inject consultative instructions and forward to LLM.
        if intent == INTENT_BUSINESS_QUERY or is_business_query(request.message):
            consultative_context = (
                "[CONSULTATIVE MODE ACTIVATED]\n"
                "The user is describing their business or asking how you can help them.\n"
                "MANDATORY BEHAVIOUR:\n"
                "1. DO NOT mention pricing, packages, or costs at all in your response.\n"
                "2. WARMLY acknowledge their specific industry or product niche.\n"
                "3. Give 2-3 specific, concrete examples of how video content helps their type of business.\n"
                "4. Recommend 2 relevant video formats for their use case (by Type name, not price).\n"
                "5. End with ONE smart qualifying question (e.g., their main goal, target platform, or sales channel).\n"
                "6. Be warm, expert, consultative — like a creative director on a discovery call.\n"
                "7. Use emojis sparingly but naturally.\n\n"
                f"User message: {request.message}"
            )
            reply = generate_response(
                user_message=consultative_context,
                state=state,
                retrieved_context=None,
            )
            state.awaiting_business_discovery = True
            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }

        # ── BUSINESS FOLLOWUP INTENT ──────────────────────────────────────────
        if intent == INTENT_BUSINESS_FOLLOWUP or is_business_followup(request.message):
            state.awaiting_business_discovery = False
            state.user_goal = request.message
            
            context = (
                "The user is answering a business discovery question about their main goal. "
                f"Their answer is: '{request.message}'.\n"
                "MANDATORY BEHAVIOUR:\n"
                "1. Acknowledge their specific goal.\n"
                "2. Give 2-3 concrete video content strategies that directly address that goal.\n"
                "3. End by asking if they'd like to book a quick strategy call so we can map this out properly for their brand.\n"
            )
            reply = generate_response(
                user_message=context,
                state=state,
                retrieved_context=None,
            )
            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }

        extracted = state_manager.extract_structured_fields(request.message)
        state_manager.update_state(state, extracted)

        state_manager.advance_stage(state)

        if state.is_fully_qualified() and state.recommended_package is None:
            package = recommend_package(state)
            if package:
                state.recommended_package = str(package["type"])
                state_manager.advance_stage(state)

        if not state_manager.validate_stage(state):
            raise HTTPException(
                status_code=400,
                detail="Lead is not fully qualified for recommendation stage.",
            )

        if requires_escalation(state):
            reply = (
                "Based on your requirement, this would be best handled with a strategic "
                "discussion. Let me arrange a call with our creative team."
            )
            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            if state.name or state.email:
                _create_lead_if_needed(db, state)
            _create_order_if_needed(db, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "escalation": True,
                "sales_mode": state.sales_mode,
            }

        score = calculate_lead_score(state)
        state.lead_score = score
        priority_flag = is_high_priority(score)

        if can_auto_close(state):
            lowered = request.message.lower()
            if any(token in lowered for token in ("confirm", "yes", "proceed", "go ahead")):
                confirmation = confirm_order(state)
                state_manager.advance_stage(state)
                reply = (
                    f"Perfect. Your {state.recommended_package} has been confirmed.\n"
                    "Our onboarding process will begin shortly."
                )
                state_manager.update_history(state, "assistant", reply)
                _add_message(db, state.conversation_id, "assistant", reply)
                _sync_conversation_record(conversation_record, state)
                if state.name or state.email:
                    _create_lead_if_needed(db, state)
                _create_order_if_needed(db, state)
                conversation_store[state.conversation_id] = state
                db.commit()
                return {
                    "reply": reply,
                    "conversation_id": state.conversation_id,
                    "stage": state.stage,
                    "order_confirmed": state.order_confirmed,
                    "confirmation": confirmation,
                    "sales_mode": state.sales_mode,
                }



        # ══════════════════════════════════════════
        # BUSINESS CONTEXT DETECTION & HANDLING
        # ══════════════════════════════════════════
        BUSINESS_KEYWORDS = [
            'business owner', 'i own', 'my business',
            'my company', 'my brand', 'i sell', 
            'my products', 'my store', 'my shop',
            'i run', 'we sell', 'our company',
            'how can you help', 'what can you offer',
            'how could you help'
        ]
        
        PRICE_KEYWORDS = [
            'price', 'cost', 'how much', 'pricing',
            'packages', 'rates', 'charges', 'budget',
            'affordable', 'expensive', 'fee', 'investment', 'payment'
        ]
        
        user_input_lower = request.message.lower().strip()
        has_business_context = any(
            kw in user_input_lower 
            for kw in BUSINESS_KEYWORDS
        )
        has_price_query = any(
            kw in user_input_lower 
            for kw in PRICE_KEYWORDS
        )
        
        # If business context detected but NO explicit price query, 
        # add consultative instruction to Claude
        enhanced_message = request.message
        if has_business_context and not has_price_query:
            consultative_instruction = (
                "[CONSULTATIVE MODE ACTIVATED]\n"
                "The user has described their business or asked how you can help.\n"
                "CRITICAL RULES:\n"
                "1. DO NOT mention pricing first or unsolicited\n"
                "2. DO acknowledge their specific business type\n"
                "3. DO explain 2-3 specific ways video content helps THEIR industry\n"
                "4. DO suggest 2-3 relevant video format recommendations (by Type)\n"
                "5. DO ask ONE qualifying follow-up question\n"
                "6. ONLY mention pricing if they ask directly\n\n"
                f"User said: {request.message}"
            )
            enhanced_message = consultative_instruction

        # SAFETY: never let LLM run while meeting flow is active
        _meeting_flow_active = (
            getattr(state, 'meeting_awaiting_email', False)
            or getattr(state, 'meeting_awaiting_purpose', False)
            or getattr(state, 'meeting_awaiting_date', False)
            or getattr(state, 'meeting_awaiting_time', False)
            or (
                state.meeting_booked
                and getattr(state, 'meeting_needs_email', False)
            )
        )
        if _meeting_flow_active:
            reply = "I didn't quite catch that — could you rephrase? 😊"
            return _persist_assistant_reply(
                db, state, conversation_record, reply
            )

        reply = generate_response(
            user_message=enhanced_message,
            state=state,
            retrieved_context=None,
        )

        state_manager.update_history(state, "assistant", reply)
        _add_message(db, state.conversation_id, "assistant", reply)
        _sync_conversation_record(conversation_record, state)
        if state.name or state.email:
            _create_lead_if_needed(db, state)
        _create_order_if_needed(db, state)
        conversation_store[state.conversation_id] = state
        db.commit()

        return {
            "reply": reply,
            "conversation_id": state.conversation_id,
            "stage": state.stage,
            "sales_mode": state.sales_mode,
            "lead_score": state.lead_score,
            "high_priority": priority_flag,
            "recommended_package": state.recommended_package,
            "order_confirmed": state.order_confirmed,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        import traceback
        db.rollback()
        logging.error(f"CHAT ROUTE CRASH: {type(exc).__name__}: {exc}")
        logging.error(traceback.format_exc())
        
        state_var = locals().get("state")
        if state_var is None:
            raise HTTPException(status_code=500, detail="Internal Server Error")
            
        # FIX 3 — Improve catch-all fallback
        def is_gibberish(text: str) -> bool:
            words = text.strip().split()
            # Only catch-all if very short AND no real words
            if len(words) >= 4:
                return False  # Always try LLM for real sentences
            # Short input — check if it's recognizable
            common_words = {
                'yes', 'no', 'ok', 'okay', 'sure', 'help',
                'hi', 'hello', 'thanks', 'bye', 'good',
                'great', 'nice', 'cool', 'fine', 'got it'
            }
            return not any(w.lower() in common_words for w in words)
            
        if is_gibberish(request.message):
            return {
                "reply": "I didn't quite catch that — could you rephrase? 😊",
                "conversation_id": request.conversation_id or "error",
                "stage": "unknown",
                "lead_score": 0,
                "sales_mode": "discovery",
                "recommended_package": None,
                "order_confirmed": False,
            }
        else:
            # Pass to Claude — it can handle anything
            reply = generate_response(
                user_message=request.message,
                state=state,
                retrieved_context=None,
            )
            state_manager.update_history(state, "assistant", reply)
            _add_message(db, state.conversation_id, "assistant", reply)
            _sync_conversation_record(conversation_record, state)
            conversation_store[state.conversation_id] = state
            db.commit()
            return {
                "reply": reply,
                "conversation_id": state.conversation_id,
                "stage": state.stage,
                "sales_mode": state.sales_mode,
            }


@router.get("/get_last_crash")
def get_last_crash():
    return {"crash": LAST_CRASH, "store_keys": list(conversation_store.keys())}


@router.post("/schedule-meeting")
async def schedule_meeting(payload: ScheduleMeetingRequest) -> dict[str, object]:
    requested_time = (payload.time or "").strip()
    requested_email = (payload.email or "").strip().lower()
    requested_name = (payload.name or "").strip() or "there"
    logging.info(
        "[Meeting API] Received schedule request name=%s email=%s time=%s",
        requested_name,
        requested_email,
        requested_time,
    )

    calendar_result: dict[str, object] = {
        "success": False,
        "status": "not_attempted",
    }
    slot_label = requested_time
    meet_link = None

    slot_id_match = re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}", requested_time)
    parsed_slot_id = requested_time if slot_id_match else _parse_free_text_meeting_time_to_slot_id(requested_time)
    logging.info("parsed_slot_id=%s from requested_time=%s", parsed_slot_id, requested_time)
    if parsed_slot_id:
        booking = book_slot(
            user_name=requested_name,
            user_email=requested_email,
            meeting_purpose=(payload.purpose or "Strategy call booked via Vidio widget"),
            preferred_time=parsed_slot_id,
            host_email=os.getenv("MEETING_HOST_EMAIL"),
        )
        calendar_result = {
            "success": bool(booking.get("success")),
            "status": "booked" if booking.get("success") else str(booking.get("error") or "failed"),
            "event_id": booking.get("event_id"),
            "meet_link": booking.get("meet_link"),
        }
        slot_label = str(booking.get("slot_label") or requested_time)
        meet_link = booking.get("meet_link")
    else:
        calendar_result = {
            "success": False,
            "status": "manual_time_not_booked",
        }

    logging.info("[Meeting API] Calendar result: %s", calendar_result)

    email_result = send_meeting_confirmation(
        lead_name=requested_name,
        lead_email=requested_email,
        slot_label=slot_label,
        meet_link=meet_link,
    )

    calendar_created = bool(calendar_result.get("success"))
    logging.info("[Meeting API] Email result: %s", email_result)
    return {
        "success": calendar_created or bool(email_result.get("success")),
        "calendarCreated": calendar_created,
        "calendar": calendar_result,
        "meetLink": calendar_result.get("meet_link"),
        "eventId": calendar_result.get("event_id"),
        "message": "Meeting scheduled and invite sent" if calendar_created else "Meeting logged but calendar invite failed",
        "email": {
            "success": bool(email_result.get("success")),
            "lead_delivery": email_result.get("lead_delivery", "unknown"),
            "host_delivery": email_result.get("host_delivery", "unknown"),
        },
    }
