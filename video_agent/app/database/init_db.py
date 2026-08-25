from sqlalchemy import inspect, text

from app.database.db import Base, engine
from app.models import db_models  # noqa: F401


def _ensure_conversation_meeting_meta_column() -> None:
    inspector = inspect(engine)
    if "conversations" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("conversations")}
    if "meeting_meta" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE conversations ADD COLUMN meeting_meta TEXT"))


def _ensure_lead_columns() -> None:
    inspector = inspect(engine)
    if "leads" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("leads")}
    with engine.begin() as connection:
        if "whatsapp_number" not in columns:
            connection.execute(text("ALTER TABLE leads ADD COLUMN whatsapp_number VARCHAR(50)"))
        if "order_intent" not in columns:
            connection.execute(text("ALTER TABLE leads ADD COLUMN order_intent BOOLEAN DEFAULT FALSE"))
        if "order_ref" not in columns:
            connection.execute(text("ALTER TABLE leads ADD COLUMN order_ref VARCHAR(50)"))


def _ensure_order_ref_column() -> None:
    inspector = inspect(engine)
    if "orders" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("orders")}
    if "order_ref" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE orders ADD COLUMN order_ref VARCHAR(50)"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_conversation_meeting_meta_column()
    _ensure_lead_columns()
    _ensure_order_ref_column()
