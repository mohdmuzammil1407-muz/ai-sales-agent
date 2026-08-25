import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database.init_db import init_db
from app.routes.auth import router as auth_router
from app.routes.admin import router as admin_router
from app.routes.chat import router as chat_router
from app.services.meeting_reminder_service import (
    start_meeting_reminder_worker,
    stop_meeting_reminder_worker,
)


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = FastAPI(title="vidio-agent", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    widget_path = os.path.join(os.path.dirname(__file__), "..", "widget")
    if os.path.exists(widget_path):
        app.mount("/widget", StaticFiles(directory=widget_path), name="widget")

    @app.on_event("startup")
    def startup() -> None:
        init_db()
        start_meeting_reminder_worker()

    @app.on_event("shutdown")
    def shutdown() -> None:
        stop_meeting_reminder_worker()

    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(auth_router)
    app.include_router(admin_router)
    return app


app = create_app()

app = create_app()
