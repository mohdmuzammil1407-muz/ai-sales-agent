from __future__ import annotations

import hashlib
import logging
import random
import re
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import AuthUser, OtpCode
from app.services.email_service import send_otp_email
logger = logging.getLogger(__name__)


def is_email(identifier: str) -> bool:
    return "@" in identifier


def normalize_identifier(identifier: str) -> str:
    value = identifier.strip()
    if is_email(value):
        return value.lower()
    return re.sub(r"[^\d+]", "", value)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_token(identifier: str) -> str:
    raw = f"{identifier}:{datetime.utcnow().isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def find_user_by_identifier(db: Session, identifier: str) -> AuthUser | None:
    normalized = normalize_identifier(identifier)
    if is_email(normalized):
        return db.query(AuthUser).filter(AuthUser.email == normalized).first()
    return db.query(AuthUser).filter(AuthUser.phone == normalized).first()


def login_user(db: Session, *, identifier: str, password: str) -> dict[str, object]:
    user = find_user_by_identifier(db, identifier)
    if user is None or not user.password_hash:
        return {"success": False, "error": "Invalid credentials"}

    if user.password_hash != hash_password(password):
        return {"success": False, "error": "Invalid credentials"}

    return {
        "success": True,
        "user": user,
        "token": create_token(user.email or user.phone or user.name),
    }


def request_otp(db: Session, *, identifier: str, name: str | None = None) -> dict[str, object]:
    normalized = normalize_identifier(identifier)
    otp_code = f"{random.randint(0, 999999):06d}"
    expiry = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

    db.add(
        OtpCode(
            identifier=normalized,
            otp_code=otp_code,
            name=name,
            expires_at=expiry,
        )
    )
    db.commit()

    logger.info("OTP generated", extra={"identifier": normalized, "channel": "email" if is_email(normalized) else "phone"})

    if is_email(normalized):
        delivery_result = send_otp_email(to_email=normalized, otp_code=otp_code, name=name)
        if delivery_result["success"]:
            return {
                "success": True,
                "delivery": "email",
                "message": f"OTP sent to {normalized}.",
            }

        logger.warning(
            "OTP persisted but email delivery failed",
            extra={"identifier": normalized, "reason": delivery_result.get("message")},
        )
        return {
            "success": True,
            "delivery": delivery_result.get("delivery", "stored_only"),
            "message": delivery_result.get("message", "OTP stored but email not sent."),
        }

    logger.info("OTP generated for phone identifier", extra={"identifier": normalized, "otp_code": otp_code})
    return {
        "success": True,
        "delivery": "phone_pending",
        "message": "OTP generated. SMS delivery is not configured yet.",
    }


def verify_otp(db: Session, *, identifier: str, otp: str, name: str | None = None) -> dict[str, object]:
    normalized = normalize_identifier(identifier)
    now = datetime.utcnow()

    otp_record = (
        db.query(OtpCode)
        .filter(OtpCode.identifier == normalized)
        .filter(OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc())
        .first()
    )

    if otp_record is None:
        return {"success": False, "error": "Invalid or expired OTP"}

    if otp_record.expires_at < now:
        db.delete(otp_record)
        db.commit()
        return {"success": False, "error": "Invalid or expired OTP"}

    if otp_record.failed_attempts >= 3:
        db.delete(otp_record)
        db.commit()
        return {"success": False, "locked": True, "message": "Too many attempts. Request a new code."}

    if otp_record.otp_code != otp:
        otp_record.failed_attempts += 1
        if otp_record.failed_attempts >= 3:
            db.delete(otp_record)
            db.commit()
            return {"success": False, "locked": True, "message": "Too many attempts. Request a new code."}
        db.commit()
        return {"success": False, "error": "Invalid OTP code"}

    db.delete(otp_record)

    user = find_user_by_identifier(db, normalized)
    if user is None:
        user = AuthUser(
            name=(name or otp_record.name or "User").strip() or "User",
            email=normalized if is_email(normalized) else None,
            phone=None if is_email(normalized) else normalized,
            auth_provider="otp",
            updated_at=now,
        )
        db.add(user)
    else:
        if name and name.strip():
            user.name = name.strip()
        user.auth_provider = "otp"
        user.updated_at = now

    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "user": user,
        "token": create_token(user.email or user.phone or user.name),
    }


def seed_password_user(
    db: Session,
    *,
    name: str,
    email: str | None = None,
    phone: str | None = None,
    password: str,
) -> AuthUser:
    identifier_filters = []
    if email:
        identifier_filters.append(AuthUser.email == email.lower())
    if phone:
        identifier_filters.append(AuthUser.phone == normalize_identifier(phone))

    existing = db.query(AuthUser).filter(or_(*identifier_filters)).first() if identifier_filters else None
    if existing:
        return existing

    user = AuthUser(
        name=name,
        email=email.lower() if email else None,
        phone=normalize_identifier(phone) if phone else None,
        password_hash=hash_password(password),
        auth_provider="password",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
