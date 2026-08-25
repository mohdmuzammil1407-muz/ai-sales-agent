import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from fastapi.testclient import TestClient
from app.main import app
import traceback

client = TestClient(app)

try:
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "Talk to the team",
            "active_flow": "meeting",
            "flow_step": "fetch_slots",
            "conversation_id": "test_conv_id_1"
        }
    )
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.json())
except Exception as e:
    print("CRASHED:", e)
    traceback.print_exc()
