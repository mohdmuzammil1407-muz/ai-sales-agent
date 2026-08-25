import requests
import time

BASE = "http://127.0.0.1:8000/api/v1/chat"

messages = [
    "Hi",
    "I run a restaurant in Chennai and need a 30 second promo video",
    "Target audience is 25-40, Instagram and Reels",
    "My budget is around 6000",
    "My name is Priya, email priya@spicegarden.in, business is Spice Garden Restaurant",
    "What package do you recommend?",
    "Yes lets proceed with that"
]

def run_test():
    conversation_id = None

    print("\n" + "="*70)
    print("REAL CONVERSATION TEST — VIDIO AI AGENT")
    print("="*70 + "\n")

    for message in messages:
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id

        try:
            response = requests.post(BASE, json=payload, timeout=30)
            data = response.json()

            conversation_id = data.get("conversation_id", conversation_id)
            reply = data.get("reply", "ERROR")
            stage = data.get("stage", "unknown")
            score = data.get("lead_score", 0)
            package = data.get("recommended_package", "none")

            print(f"USER  : {message}")
            print(f"VIDIO : {reply}")
            print(f"Stage : {stage} | Score: {score} | Package: {package}")
            print("-" * 70)

            time.sleep(1)

        except Exception as e:
            print(f"ERROR: {str(e)}")
            break

    print(f"\nConversation ID: {conversation_id}")
    print("\nNow check your dashboard at http://localhost:3000/dashboard")

if __name__ == "__main__":
    run_test()
