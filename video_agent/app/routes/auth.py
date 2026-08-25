from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.database.db import get_db
from app.services.auth_service import login_user, request_otp, verify_otp
from app.services.email_service import get_smtp_status, send_test_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str = Field(..., min_length=1)


class OtpRequest(BaseModel):
    identifier: str = Field(..., min_length=3)
    name: str | None = None


class OtpVerifyRequest(BaseModel):
    identifier: str = Field(..., min_length=3)
    otp: str = Field(..., min_length=4, max_length=6)
    name: str | None = None


class SmtpTestRequest(BaseModel):
    email: str = Field(..., min_length=5)
    subject: str | None = None


def _serialize_user(user) -> dict[str, str | None]:
    return {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
    }


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    identifier = request.email or request.phone
    if not identifier:
        raise HTTPException(status_code=400, detail="Email or phone is required")

    result = login_user(db, identifier=identifier, password=request.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])

    return {
        "token": result["token"],
        "user": _serialize_user(result["user"]),
    }


@router.post("/otp/request")
async def otp_request(request: OtpRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    result = request_otp(db, identifier=request.identifier, name=request.name)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    payload: dict[str, object] = {"success": True, "delivery": result.get("delivery")}
    if result.get("message"):
        payload["message"] = result["message"]
    return payload


@router.post("/otp/verify")
async def otp_verify(request: OtpVerifyRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    result = verify_otp(
        db,
        identifier=request.identifier,
        otp=request.otp,
        name=request.name,
    )
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])

    return {
        "token": result["token"],
        "user": _serialize_user(result["user"]),
    }


@router.get("/otp/status")
async def otp_status() -> dict[str, object]:
    smtp_status = get_smtp_status()
    return {
        "success": True,
        "smtp": smtp_status,
        "email_otp_ready": bool(smtp_status["configured"]),
        "phone_otp_ready": False,
    }


@router.post("/otp/test-email")
async def otp_test_email(request: SmtpTestRequest) -> dict[str, object]:
    result = send_test_email(to_email=request.email, subject=request.subject)
    if not result["success"]:
        raise HTTPException(
            status_code=400 if result.get("delivery") == "not_configured" else 500,
            detail=result.get("message", "Failed to send test email"),
        )

    return {
        "success": True,
        "delivery": result.get("delivery"),
        "smtp": result.get("smtp"),
        "message": f"Test email sent to {request.email}.",
    }
