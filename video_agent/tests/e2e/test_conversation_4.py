import requests
import time

BASE = "http://127.0.0.1:8000/api/v1/chat"

messages = [
    "Hi there",
    "I have a small bakery in Kochi called Sweet Corner. Need a short promo video for social media",
    "Something simple, just showing our cakes and pastries",
    "My budget is only 1500 rupees. Is that possible?",
    "That seems expensive for a small business. Can you reduce the price?",
    "What will I actually get in the basic package?",
    "Will it look professional or cheap?",
    "Okay what if I go with the 1899 option instead",
    "My name is Meera, email meera@sweetcorner.in, business Sweet Corner Bakery",
    "Timeline is flexible, maybe 2 weeks",
    "Alright lets go with Type 2 package",
    "Can I speak to someone from your team before paying?"
]

def run_test():
    conversation_id = None
    print("\n" + "="*70)
    print("TEST 4 — MEERA SWEET CORNER BAKERY — BUDGET OBJECTIONS")
    print("="*70 + "\n")

    for message in messages:
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        try:
            response = requests.post(BASE, json=payload, timeout=30)
            data = response.json()
            conversation_id = data.get("conversation_id", conversation_id)
            print(f"USER  : {message}")
            print(f"VIDIO : {data.get('reply', 'ERROR')}")
            print(f"Stage : {data.get('stage')} | Score: {data.get('lead_score')} | Package: {data.get('recommended_package')}")
            print("-" * 70)
            time.sleep(1)
        except Exception as e:
            print(f"ERROR: {str(e)}")
            break

    print(f"\nConversation ID: {conversation_id}")

if __name__ == "__main__":
    run_test()
