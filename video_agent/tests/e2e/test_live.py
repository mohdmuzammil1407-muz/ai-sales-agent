import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import requests

url = "http://127.0.0.1:8000/api/v1/chat"
s = requests.Session()

# 1. Start a chat
resp1 = s.post(url, json={"message": "hello", "bootstrap_identity": True})
print("Start:", resp1.json())
cid = resp1.json().get("conversation_id")

# 2. Click "Talk to the team"
resp2 = s.post(url, json={
    "message": "I want to schedule a call with the team",
    "active_flow": "meeting",
    "flow_step": "fetch_slots",
    "conversation_id": cid
})
print("Meeting:", resp2.json())
