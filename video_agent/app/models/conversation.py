from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ConversationState(BaseModel):
    conversation_id: str
    stage: str = "greeting"

    name: Optional[str] = None
    email: Optional[str] = None
    business_name: Optional[str] = None
    mood: Optional[str] = None
    creative_direction: Optional[str] = None

    video_type: Optional[str] = None
    target_audience: Optional[str] = None
    timeline: Optional[str] = None
    budget: Optional[int] = None

    recommended_package: Optional[str] = None
    lead_score: int = 0
    order_confirmed: bool = False
    whatsapp_number: Optional[str] = None
    order_ref: Optional[str] = None
    order_intent: bool = False
    user_style: Optional[str] = "neutral"
    last_objection: Optional[str] = None
    message_count: int = 0
    sales_mode: Literal["discovery", "consultative", "closing", "support"] = "discovery"
    meeting_requested: bool = False
    meeting_awaiting_purpose: bool = False
    meeting_purpose: Optional[str] = None
    meeting_awaiting_date: bool = False
    meeting_awaiting_time: bool = False
    meeting_selected_date_id: str = ""
    meeting_selected_date_label: str = ""
    meeting_available_dates: List[Dict[str, str]] = Field(default_factory=list)
    meeting_available_times: List[Dict[str, str]] = Field(default_factory=list)
    meeting_booked: bool = False
    meeting_slot_label: str = ""
    meeting_event_id: str = ""
    meeting_slot_start_iso: str = ""
    meeting_needs_email: bool = False
    meeting_reminder_sent: bool = False
    meeting_awaiting_email: bool = False
    active_flow: Optional[str] = None
    flow_step: Optional[str] = None
    # ── Business discovery context ───────────────────────────────────────────
    # Set to True after the bot asks a qualifying question (e.g. "what's your
    # main goal?"). Checked on the NEXT turn so the follow-up answer is routed
    # to the LLM with goal context instead of falling through to stage-validation.
    awaiting_business_discovery: bool = False
    user_goal: Optional[str] = None

    conversation_history: List[Dict[str, str]] = Field(default_factory=list)

    def is_fully_qualified(self) -> bool:
        required_values = (
            self.name,
            self.email,
            self.business_name,
            self.video_type,
            self.target_audience,
            self.timeline,
            self.budget,
        )
        return all(value is not None for value in required_values)
