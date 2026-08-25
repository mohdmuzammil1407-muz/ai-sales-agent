from app.models.conversation import ConversationState
from app.routes.chat import _build_product_discovery_reply, _is_product_description_message
from app.services.objection_service import OBJECTION_NONE, detect_objection


def test_high_quality_product_description_is_not_quality_objection() -> None:
    message = (
        "my product is an water bottle,it has speciality of high quality plastic, "
        "lightweight, and have attractive colours options."
    )

    assert detect_objection(message) == OBJECTION_NONE


def test_product_description_message_gets_contextual_follow_up() -> None:
    state = ConversationState(conversation_id="test-conversation")
    message = (
        "my product is an water bottle,it has speciality of high quality plastic, "
        "lightweight, and have attractive colours options."
    )

    assert _is_product_description_message(message) is True

    reply = _build_product_discovery_reply(message, state)

    assert "water bottle" in reply.lower()
    assert "lightweight" in reply.lower()
    assert "who are you mainly trying to sell it to" in reply.lower()
