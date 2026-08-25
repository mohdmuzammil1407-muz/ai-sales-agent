import requests
import time

BASE = "http://127.0.0.1:8000/api/v1/chat"

messages = [
    "Hey",
    "I am a food influencer with 200k followers on Instagram. I want a UGC style ad for a restaurant client of mine",
    "The restaurant is called Masala Trails, it is a north Indian fine dining place in Bangalore",
    "I want the video to look authentic, not overly produced. Real food shots with my voiceover",
    "Budget is 7000 and I need it in 10 days",
    "My name is Sneha, email sneha@foodie.in",
    "Will you write the script or do I provide it?",
    "I will provide the script. Can you add subtitles in English?",
    "Also need it in both 16:9 and 9:16 formats",
    "What package fits this best?",
    "Yes lets confirm that package"
]

def run_test():
    conversation_id = None
    print("\n" + "="*70)
    print("TEST 3 — SNEHA FOOD INFLUENCER — UGC AD")
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
