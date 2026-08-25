import requests
import time
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
CHAT_URL = f"{BASE_URL}/api/v1/chat"
ADMIN_URL = f"{BASE_URL}/api/v1/admin"

def get_admin_token() -> str:
    r = requests.post(
        f"{ADMIN_URL}/login",
        json={"email": "admin@ilmora.ai", "password": "admin123"}
    )
    if r.status_code == 200:
        return r.json()["token"]
    return ""

def send_message(message: str, conversation_id: str = None) -> dict:
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    try:
        r = requests.post(CHAT_URL, json=payload, timeout=30)
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}", "reply": "ERROR"}
    except Exception as e:
        return {"error": str(e), "reply": "ERROR"}

def evaluate_response(
    user_msg: str,
    reply: str,
    expected_keywords: list,
    forbidden_keywords: list = []
) -> dict:
    reply_lower = reply.lower()
    found = [kw for kw in expected_keywords if kw.lower() in reply_lower]
    forbidden_found = [kw for kw in forbidden_keywords if kw.lower() in reply_lower]
    score = (len(found) / len(expected_keywords) * 10) if expected_keywords else 5
    if forbidden_found:
        score = max(0, score - len(forbidden_found) * 2)
    return {
        "score": round(min(score, 10), 1),
        "found": found,
        "missing": [kw for kw in expected_keywords if kw.lower() not in reply_lower],
        "forbidden_found": forbidden_found,
        "passed": score >= 6 and not forbidden_found
    }

def run_persona_test(persona_name: str, messages_with_checks: list) -> dict:
    print(f"\n{'='*70}")
    print(f"PERSONA: {persona_name}")
    print(f"{'='*70}")

    conversation_id = None
    results = []
    total_score = 0

    for item in messages_with_checks:
        user_msg = item["message"]
        expected = item.get("expected", [])
        forbidden = item.get("forbidden", [])

        data = send_message(user_msg, conversation_id)
        conversation_id = data.get("conversation_id", conversation_id)
        reply = data.get("reply", "ERROR")
        stage = data.get("stage", "unknown")
        score_val = data.get("lead_score", 0)
        package = data.get("recommended_package", "none")

        eval_result = evaluate_response(user_msg, reply, expected, forbidden)
        total_score += eval_result["score"]

        status = "✅ PASS" if eval_result["passed"] else "❌ FAIL"

        print(f"\nUSER  : {user_msg}")
        print(f"VIDIO : {reply[:150]}{'...' if len(reply) > 150 else ''}")
        print(f"Stage : {stage} | Lead Score: {score_val} | Package: {package}")
        print(f"Eval  : {status} | Score: {eval_result['score']}/10")
        if eval_result["missing"]:
            print(f"Missing: {eval_result['missing']}")
        if eval_result["forbidden_found"]:
            print(f"Bad phrases: {eval_result['forbidden_found']}")
        print("-" * 70)

        results.append({
            "message": user_msg,
            "reply": reply,
            "stage": stage,
            "eval": eval_result
        })

        time.sleep(1.5)

    avg = total_score / len(results) if results else 0
    print(f"\n📊 {persona_name} — Avg Score: {round(avg, 1)}/10")
    return {
        "persona": persona_name,
        "conversation_id": conversation_id,
        "avg_score": round(avg, 1),
        "results": results
    }

def check_dashboard(token: str, conversation_ids: list):
    print(f"\n{'='*70}")
    print("DASHBOARD VERIFICATION")
    print(f"{'='*70}")

    headers = {"Authorization": f"Bearer {token}"}

    # Check conversations
    r = requests.get(f"{ADMIN_URL}/conversations", headers=headers)
    convs = r.json() if r.status_code == 200 else []
    print(f"\n✅ Total conversations in DB: {len(convs)}")

    # Check leads
    r2 = requests.get(f"{ADMIN_URL}/leads", headers=headers)
    leads = r2.json() if r2.status_code == 200 else []
    print(f"✅ Total leads in DB: {len(leads)}")

    # Check each test conversation
    for cid in conversation_ids:
        if not cid:
            continue
        r3 = requests.get(f"{ADMIN_URL}/chats/{cid}", headers=headers)
        if r3.status_code == 200:
            chat = r3.json()
            msg_count = len(chat.get("messages", []))
            name = chat.get("name", "Anonymous")
            print(f"✅ Conv {cid[:8]}... → {name} | {msg_count} messages | Stage: {chat.get('stage')}")
        else:
            print(f"❌ Conv {cid[:8]}... → Not found in DB")

PERSONAS = [

    {
        "name": "Riya — Luxury Fashion Brand",
        "messages": [
            {
                "message": "Hi",
                "expected": ["vidio", "video", "create"],
                "forbidden": ["error"]
            },
            {
                "message": "I run a luxury fashion brand called Riya Couture. We need a brand video for our new collection launch on Instagram",
                "expected": ["brand", "video", "package", "instagram"],
                "forbidden": ["restaurant", "food", "error"]
            },
            {
                "message": "Target audience is women 25 to 45, high income. We want something editorial and cinematic",
                "expected": ["cinematic", "audience", "package"],
                "forbidden": ["error"]
            },
            {
                "message": "Budget is around 12000 and timeline is 3 weeks",
                "expected": ["package", "price", "₹"],
                "forbidden": ["error", "1199"]
            },
            {
                "message": "My name is Riya Sharma, email riya@riyacouture.com, business Riya Couture",
                "expected": ["riya", "package", "proceed"],
                "forbidden": ["error"]
            },
            {
                "message": "What exactly is included in the package you recommend?",
                "expected": ["included", "package", "ultra hd"],
                "forbidden": ["error"]
            },
            {
                "message": "Can we add a professional voiceover to narrate the collection story?",
                "expected": ["voiceover", "add-on", "package"],
                "forbidden": ["error"]
            },
            {
                "message": "Summarize the package, price, duration and deliverables",
                "expected": ["package", "price", "duration", "deliverables"],
                "forbidden": ["error"]
            },
            {
                "message": "Confirmed. Lets proceed",
                "expected": ["confirmed", "onboarding", "ilmora"],
                "forbidden": ["error"]
            }
        ]
    },

    {
        "name": "Kiran — Tech Startup Product Launch",
        "messages": [
            {
                "message": "Hello",
                "expected": ["vidio", "video"],
                "forbidden": ["error"]
            },
            {
                "message": "We are a B2B SaaS startup called DataSync launching a product demo video for LinkedIn and YouTube",
                "expected": ["video", "package", "brand"],
                "forbidden": ["restaurant", "food", "error"]
            },
            {
                "message": "Our audience is CTOs and product managers aged 30 to 50",
                "expected": ["audience", "package"],
                "forbidden": ["error"]
            },
            {
                "message": "Budget is 8000, need it in 2 weeks",
                "expected": ["package", "₹", "price"],
                "forbidden": ["error", "1199"]
            },
            {
                "message": "I am Kiran, email kiran@datasync.io, company DataSync Technologies",
                "expected": ["kiran", "package"],
                "forbidden": ["error"]
            },
            {
                "message": "Do you handle motion graphics for the product UI walkthrough?",
                "expected": ["motion", "graphics", "package"],
                "forbidden": ["error"]
            },
            {
                "message": "Can I see this in two formats — landscape for YouTube and vertical for LinkedIn?",
                "expected": ["format", "16:9", "9:16"],
                "forbidden": ["error"]
            },
            {
                "message": "Yes lets go ahead and confirm",
                "expected": ["confirmed", "onboarding"],
                "forbidden": ["error"]
            }
        ]
    },

    {
        "name": "Ahmed — Budget Conscious Local Business",
        "messages": [
            {
                "message": "Hi I need a video",
                "expected": ["vidio", "video", "create"],
                "forbidden": ["error"]
            },
            {
                "message": "Small mobile repair shop in Calicut. Need something for WhatsApp status and Instagram stories",
                "expected": ["video", "package", "social"],
                "forbidden": ["error"]
            },
            {
                "message": "Very tight budget, maximum 1200 rupees",
                "expected": ["1199", "type 1", "package"],
                "forbidden": ["error", "5999", "6999"]
            },
            {
                "message": "What is included in that package exactly?",
                "expected": ["15", "single", "character", "social"],
                "forbidden": ["error"]
            },
            {
                "message": "My name is Ahmed, email ahmed@mobilefix.in",
                "expected": ["ahmed", "package"],
                "forbidden": ["error"]
            },
            {
                "message": "Can you reduce the price at all?",
                "expected": ["quality", "value", "package"],
                "forbidden": ["error"]
            },
            {
                "message": "Okay I will go with the basic package",
                "expected": ["confirmed", "package"],
                "forbidden": ["error"]
            }
        ]
    }

]

def main():
    print("\n" + "="*70)
    print("VIDIO AI AGENT — FULL SIMULATION TEST")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Get admin token for dashboard check
    token = get_admin_token()
    if token:
        print("✅ Admin login successful")
    else:
        print("⚠️  Admin login failed — dashboard check will be skipped")

    # Run all persona tests
    all_results = []
    conversation_ids = []

    for persona in PERSONAS:
        result = run_persona_test(persona["name"], persona["messages"])
        all_results.append(result)
        if result["conversation_id"]:
            conversation_ids.append(result["conversation_id"])
        time.sleep(2)

    # Dashboard verification
    if token:
        check_dashboard(token, conversation_ids)

    # Final report
    print(f"\n{'='*70}")
    print("FINAL SIMULATION REPORT")
    print(f"{'='*70}")

    total_avg = sum(r["avg_score"] for r in all_results) / len(all_results)

    for r in all_results:
        bar = "█" * int(r["avg_score"]) + "░" * (10 - int(r["avg_score"]))
        passed = sum(1 for res in r["results"] if res["eval"]["passed"])
        total = len(r["results"])
        print(f"{bar} {r['avg_score']}/10 | {passed}/{total} passed | {r['persona']}")

    grade = "A" if total_avg >= 8 else "B" if total_avg >= 6 else "C" if total_avg >= 4 else "D"
    print(f"\nOverall Average : {round(total_avg, 1)}/10")
    print(f"Overall Grade   : {grade}")
    print(f"Conversations   : {len(conversation_ids)} saved")
    print(f"\nCheck dashboard : http://localhost:3000/dashboard")
    print(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
