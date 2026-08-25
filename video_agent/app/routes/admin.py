from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import jwt
import os
import logging
import json
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models.db_models import Conversation as ConversationModel
from app.models.db_models import Lead as LeadModel
from app.models.db_models import Message as MsgModel
from app.models.db_models import Order as OrderModel

load_dotenv(override=True)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
security = HTTPBearer()

import sys

def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value or not value.strip():
        print(f"[FATAL] Required environment variable '{key}' is not set.")
        print(f"[FATAL] Server cannot start without '{key}'. Set it in .env")
        sys.exit(1)
    return value.strip()

ADMIN_EMAIL = _require_env("ADMIN_EMAIL")
ADMIN_PASSWORD = _require_env("ADMIN_PASSWORD")
JWT_SECRET = _require_env("JWT_SECRET")
JWT_ALGORITHM = "HS256"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _latest_lead_for_conversation(db: Session, conversation_id: str) -> LeadModel | None:
    return (
        db.query(LeadModel)
        .filter(LeadModel.conversation_id == conversation_id)
        .order_by(LeadModel.updated_at.desc(), LeadModel.created_at.desc(), LeadModel.id.desc())
        .first()
    )


def _db_messages_for_conversation(db: Session, conversation_id: str) -> list[MsgModel]:
    return (
        db.query(MsgModel)
        .filter(MsgModel.conversation_id == conversation_id)
        .order_by(MsgModel.timestamp.asc(), MsgModel.id.asc())
        .all()
    )


def _format_db_messages(db_messages: list[MsgModel]) -> list[dict[str, object]]:
    sorted_messages = sorted(
        db_messages,
        key=lambda message: (message.timestamp or datetime.min, message.id or 0),
    )

    return [
        {
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp.isoformat() if message.timestamp else None,
        }
        for message in sorted_messages
        if message.role and message.content
    ]


def _parse_meeting_meta(raw_meta: str | None) -> dict[str, object]:
    if not raw_meta:
        return {}
    try:
        parsed = json.loads(raw_meta)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _conversation_snapshot(db: Session, conv: ConversationModel) -> dict[str, object]:
    from app.routes.chat import conversation_store

    db_messages = _db_messages_for_conversation(db, conv.conversation_id)
    formatted_messages = _format_db_messages(db_messages)
    lead = _latest_lead_for_conversation(db, conv.conversation_id)
    memory = conversation_store.get(conv.conversation_id)
    meeting_meta = _parse_meeting_meta(conv.meeting_meta)
    last_message = formatted_messages[-1] if formatted_messages else None
    last_activity = last_message["timestamp"] if last_message else (
        conv.created_at.isoformat() if conv.created_at else None
    )

    lead_payload = {
        "email": getattr(memory, "email", None) or (lead.email if lead else None),
        "business": getattr(memory, "business_name", None) or (lead.business_name if lead else None),
        "score": getattr(memory, "lead_score", conv.lead_score) if memory else conv.lead_score,
        "stage": getattr(memory, "stage", None) or conv.stage,
    }

    return {
        "conversation_id": conv.conversation_id,
        "id": conv.conversation_id,
        "user_name": getattr(memory, "name", None) or (lead.name if lead else None),
        "stage": getattr(memory, "stage", None) or conv.stage,
        "lead_score": getattr(memory, "lead_score", conv.lead_score) if memory else conv.lead_score,
        "recommended_package": (
            getattr(memory, "recommended_package", None)
            or (lead.recommended_package if lead else None)
            or conv.recommended_package
        ),
        "order_confirmed": (
            getattr(memory, "order_confirmed", conv.order_confirmed) if memory else conv.order_confirmed
        ),
        "message_count": len(formatted_messages),
        "name": getattr(memory, "name", None) or (lead.name if lead else None),
        "email": getattr(memory, "email", None) or (lead.email if lead else None),
        "business_name": getattr(memory, "business_name", None) or (lead.business_name if lead else None),
        "video_type": getattr(memory, "video_type", None) or (lead.video_type if lead else None),
        "target_audience": getattr(memory, "target_audience", None) or (lead.target_audience if lead else None),
        "timeline": getattr(memory, "timeline", None) or (lead.timeline if lead else None),
        "budget": getattr(memory, "budget", None) or (lead.budget if lead else None),
        "sales_mode": getattr(memory, "sales_mode", "discovery") if memory else "discovery",
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "last_activity": last_activity,
        "last_message": last_message["content"] if last_message else None,
        "lead": lead_payload,
        "meeting": {
            "requested": bool(meeting_meta.get("meeting_requested")),
            "booked": bool(meeting_meta.get("meeting_booked")),
            "slot_label": meeting_meta.get("meeting_slot_label"),
            "event_id": meeting_meta.get("meeting_event_id"),
            "slot_start_iso": meeting_meta.get("meeting_slot_start_iso"),
            "needs_email": bool(meeting_meta.get("meeting_needs_email")),
            "reminder_sent": bool(meeting_meta.get("meeting_reminder_sent")),
        },
    }


class LoginRequest(BaseModel):
    email: str
    password: str


class EmailFollowupRequest(BaseModel):
    lead_id: str
    email_type: str


def create_token(email: str) -> str:
    payload = {
        "sub": email,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/login")
async def login(request: LoginRequest):
    logger.info(f"Login attempt for: {request.email}")
    logger.info(f"ADMIN_EMAIL loaded: {ADMIN_EMAIL}")
    logger.info(f"Password match: {request.password == ADMIN_PASSWORD}")

    if request.email == ADMIN_EMAIL and request.password == ADMIN_PASSWORD:
        token = create_token(request.email)
        return {
            "token": token,
            "email": request.email,
            "message": "Login successful"
        }

    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/conversations")
async def get_conversations(
    token=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        conversations = db.query(ConversationModel).order_by(
            ConversationModel.created_at.desc()
        ).all()
        payload = [_conversation_snapshot(db, conv) for conv in conversations]
        logger.info("Admin conversations response: %s", payload)
        return payload
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        return []


@router.get("/overview")
async def get_dashboard_overview(
    token=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        total_chats = db.query(ConversationModel).count()
        total_leads = db.query(LeadModel).count()

        total_meetings = 0
        conversations = db.query(ConversationModel).all()
        for conv in conversations:
            if conv.meeting_meta:
                try:
                    meeting_meta = json.loads(conv.meeting_meta)
                    if meeting_meta.get("meeting_booked"):
                        total_meetings += 1
                except (TypeError, ValueError):
                    logger.warning("Invalid meeting_meta for conversation %s", conv.conversation_id)

        pending_leads = (
            db.query(LeadModel)
            .join(ConversationModel, LeadModel.conversation_id == ConversationModel.conversation_id)
            .filter(ConversationModel.order_confirmed == False)
            .count()
        )

        recent_leads = (
            db.query(LeadModel, ConversationModel)
            .outerjoin(ConversationModel, LeadModel.conversation_id == ConversationModel.conversation_id)
            .order_by(LeadModel.created_at.desc())
            .limit(5)
            .all()
        )

        return {
            "total_chats": total_chats,
            "total_meetings": total_meetings,
            "total_leads": total_leads,
            "pending_leads": pending_leads,
            "recent_leads": [
                {
                    "conversation_id": lead.conversation_id,
                    "name": lead.name,
                    "email": lead.email,
                    "business_name": lead.business_name,
                    "score": lead.lead_score,
                    "status": ("confirmed" if conv and conv.order_confirmed else "pending"),
                    "recommended_package": lead.recommended_package,
                    "order_confirmed": bool(conv.order_confirmed) if conv else False,
                    "created_at": lead.created_at.isoformat() if lead.created_at else None,
                }
                for lead, conv in recent_leads
            ],
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads")
async def get_leads(
    token=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(
            LeadModel,
            ConversationModel
        ).outerjoin(
            ConversationModel,
            LeadModel.conversation_id == ConversationModel.conversation_id
        ).order_by(LeadModel.created_at.desc())
        
        db_leads = query.all()
        result = []

        for lead, conv in db_leads:
            if conv is not None:
                snapshot = _conversation_snapshot(db, conv)
            else:
                db_messages = _db_messages_for_conversation(db, lead.conversation_id)
                merged_messages = _format_db_messages(db_messages)
                snapshot = {
                    "conversation_id": lead.conversation_id,
                    "stage": None,
                    "lead_score": lead.lead_score,
                    "recommended_package": lead.recommended_package,
                    "order_confirmed": False,
                    "message_count": len(merged_messages),
                    "sales_mode": "discovery",
                    "created_at": lead.created_at.isoformat() if lead.created_at else None,
                    "last_activity": (
                        merged_messages[-1]["timestamp"] if merged_messages else None
                    ),
                    "meeting": {
                        "requested": False,
                        "booked": False,
                        "slot_label": None,
                        "event_id": None,
                        "slot_start_iso": None,
                        "needs_email": False,
                        "reminder_sent": False,
                    },
                }

            result.append({
                "id": snapshot["conversation_id"],
                "conversation_id": snapshot["conversation_id"],
                "name": lead.name,
                "email": lead.email,
                "phone": getattr(lead, "phone", None),
                "whatsapp_number": getattr(lead, "whatsapp_number", None),
                "recommended_package": lead.recommended_package,
                "order_confirmed": bool(conv.order_confirmed) if conv else False,
                "created_at": lead.created_at.isoformat() if hasattr(lead, "created_at") and lead.created_at else None,
            })

        payload = {"leads": result, "pending_followups": 0}
        logger.info("Admin leads response: %s", payload)
        return payload
    except Exception as e:
        logger.error(f"Error fetching leads: {e}")
        return {"leads": [], "pending_followups": 0}


@router.get("/overview")
async def get_overview(
    token=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        conversations = db.query(ConversationModel).all()
        leads = db.query(LeadModel).all()
        orders = db.query(OrderModel).all()

        snapshots = [_conversation_snapshot(db, conv) for conv in conversations]
        meetings_booked = sum(1 for item in snapshots if item["meeting"]["booked"])
        meeting_requests = sum(1 for item in snapshots if item["meeting"]["requested"])
        total_messages = sum(int(item["message_count"]) for item in snapshots)
        confirmed_orders = sum(1 for order in orders if order.status == "confirmed")

        return {
            "total_conversations": len(conversations),
            "total_leads": len(leads),
            "total_orders": len(orders),
            "confirmed_orders": confirmed_orders,
            "meeting_requests": meeting_requests,
            "meetings_booked": meetings_booked,
            "total_messages": total_messages,
            "high_intent_leads": sum(1 for lead in leads if (lead.lead_score or 0) >= 70),
            "pending_followups": sum(1 for item in snapshots if not item["order_confirmed"] and item["lead_score"] >= 1),
            "recent_conversations": snapshots[:10],
        }
    except Exception as e:
        logger.error(f"Error fetching overview: {e}")
        return {
            "total_conversations": 0,
            "total_leads": 0,
            "total_orders": 0,
            "confirmed_orders": 0,
            "meeting_requests": 0,
            "meetings_booked": 0,
            "total_messages": 0,
            "high_intent_leads": 0,
            "pending_followups": 0,
            "recent_conversations": [],
        }

@router.delete("/conversations/all")
async def delete_all_conversations(
    token=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        from app.routes.chat import conversation_store
        count = db.query(ConversationModel).count()
        db.query(MsgModel).delete()
        db.query(LeadModel).delete()
        db.query(ConversationModel).delete()
        db.commit()
        conversation_store.clear()
        return {"status": "all_deleted", "count": count}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting all conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    token=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        from app.routes.chat import conversation_store
        conv = db.query(ConversationModel).filter(
            ConversationModel.conversation_id == conversation_id
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        db.query(MsgModel).filter(MsgModel.conversation_id == conversation_id).delete()
        db.query(LeadModel).filter(LeadModel.conversation_id == conversation_id).delete()
        db.query(ConversationModel).filter(
            ConversationModel.conversation_id == conversation_id
        ).delete()
        db.commit()
        conversation_store.pop(conversation_id, None)
        return {"status": "deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chats/{conversation_id}")
async def get_chat(
    conversation_id: str,
    token=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        from app.routes.chat import conversation_store
        state = conversation_store.get(conversation_id)
        conv = db.query(ConversationModel).filter(
            ConversationModel.conversation_id == conversation_id
        ).first()

        if not conv and not state:
            raise HTTPException(status_code=404, detail="Conversation not found")

        db_messages = db.query(MsgModel).filter(
            MsgModel.conversation_id == conversation_id
        ).order_by(MsgModel.timestamp.asc()).all()

        lead = _latest_lead_for_conversation(db, conversation_id)
        formatted_messages = _format_db_messages(db_messages)

        resolved_name = (
            (state.name if state else None)
            or (lead.name if lead else None)
        )
        resolved_email = (
            (state.email if state else None)
            or (lead.email if lead else None)
        )
        resolved_business_name = (
            (state.business_name if state else None)
            or (lead.business_name if lead else None)
        )
        resolved_stage = state.stage if state else (conv.stage if conv else None)
        resolved_lead_score = state.lead_score if state else (conv.lead_score if conv else 0)


        logger.info("===== ADMIN CHAT DEBUG =====")
        logger.info(f"Conversation ID: {conversation_id}")
        logger.info(f"DB messages fetched: {len(db_messages)}")
        for i, message in enumerate(db_messages):
            preview = (message.content or "")[:50]
            logger.info(f"{i}: {message.role} -> {preview}")
        logger.info(f"[ADMIN CHAT FINAL] messages count: {len(formatted_messages)}")

        payload = {
            "id": conversation_id,
            "user_name": resolved_name,
            "lead": {
                "email": resolved_email,
                "business": resolved_business_name,
                "score": resolved_lead_score,
                "stage": resolved_stage,
            },
            "messages": formatted_messages,
        }
        logger.info("Admin chat response for %s: %s", conversation_id, payload)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/followup")
async def send_followup(
    request: EmailFollowupRequest,
    token=Depends(verify_token)
):
    return {
        "status": "queued",
        "lead_id": request.lead_id,
        "email_type": request.email_type,
        "message": "Email queued successfully"
    }


@router.get("/debug/messages/{conversation_id}")
async def debug_messages(
    conversation_id: str,
    token=Depends(verify_token),
    db: Session = Depends(get_db)
):
    db_messages = _db_messages_for_conversation(db, conversation_id)
    return {
        "count": len(db_messages),
        "messages": [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in db_messages
        ],
    }


@router.get("/meetings")
async def get_meetings(
    token=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        conversations = db.query(ConversationModel).order_by(
            ConversationModel.created_at.desc()
        ).all()
        meetings: list[dict[str, object]] = []

        for conv in conversations:
            snapshot = _conversation_snapshot(db, conv)
            meeting = snapshot["meeting"]
            if not isinstance(meeting, dict):
                continue

            if not (meeting.get("requested") or meeting.get("booked")):
                continue

            meetings.append(
                {
                    "id": snapshot["conversation_id"],
                    "conversation_id": snapshot["conversation_id"],
                    "user_name": snapshot.get("name"),
                    "user_email": snapshot.get("email"),
                    "purpose": "Strategy call booked via Vidio AI chat.",
                    "preferred_time": meeting.get("slot_start_iso"),
                    "created_at": snapshot.get("created_at"),
                    "calendar_status": "confirmed" if meeting.get("booked") else "pending",
                    "meet_link": None,
                    "meeting": meeting,
                    "lead": snapshot.get("lead"),
                }
            )

        payload = {"meetings": meetings}
        logger.info("Admin meetings response: %s", payload)
        return payload
    except Exception as e:
        logger.error(f"Error fetching meetings: {e}")
        return {"meetings": []}
