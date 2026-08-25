import json
import time

import requests

BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = "http://localhost:8000/api/v1/chat"

TEST_MESSAGES = [
    "Hey, I run a fine-dining restaurant in Chennai. I need a 30-sec promo with cinematic ambience shots, steam/food closeups, and a premium mood. Can you do this in 10 days?",
    "Audience is 22–40, mostly Instagram and YouTube Shorts. I want it classy, not loud. Do you understand this tone?",
    "I saw your 30-sec pricing. Be exact: what am I paying, what's included, and what's excluded?",
    "I need 2 versions: one for reels, one for stories. Same shoot concept, minor edit changes. Will that cost extra?",
    "Can you include script + voiceover + subtitles in English and Tamil under the same package?",
    "I want realistic food textures and restaurant ambience transitions. No generic stock look.",
    "My budget is ₹5000, but I want premium quality close to your higher package. What can you do?",
    "If I confirm today, can you offer discount or bonus deliverables?",
    "What if I need 45 seconds instead of 30 after project starts?",
    "I don't want to pay full upfront. Can we do milestone payments?",
    "Can I get 2 revision rounds? What happens if I ask for major changes after final render?",
    "I need this before a festival campaign. If delayed, what is your commitment?",
    "Also need one UGC-style cut with voiceover. Is that same package or separate?",
    "Can I speak to a human to finalize pricing and timeline?",
    "Okay, recommend the best package for my case now.",
    "Before confirming, summarize package, price, duration, and exact deliverables in 4 lines.",
    "Proceed. Confirm the order.",
    "Book a meeting tomorrow 5 PM IST and send invite to owner@myrestaurant.in.",
]

EXPECTED_BEHAVIORS = {
    1: {
        "check": ["Type 6", "5999", "10 days", "restaurant", "feasib"],
        "must_not": ["what kind of video", "what is your budget", "nice concept"],
        "label": "High-intent brief recognition",
    },
    2: {
        "check": ["classy", "cinematic", "22", "Instagram", "Shorts"],
        "must_not": ["what audience", "who are you targeting"],
        "label": "Tone understanding",
    },
    3: {
        "check": ["5999", "included", "excluded", "Ultra HD", "30"],
        "must_not": ["packages start from", "1199", "depends on"],
        "label": "Exact pricing transparency",
    },
    4: {
        "check": ["reels", "stories", "format", "export", "same"],
        "must_not": ["packages start from", "what type of video"],
        "label": "Multi-format handling",
    },
    5: {
        "check": ["script", "voiceover", "subtitles", "add-on", "Tamil"],
        "must_not": ["we don't", "not included", "cannot"],
        "label": "Add-on handling",
    },
    6: {
        "check": ["realistic", "texture", "ambience", "cinematic", "AI"],
        "must_not": ["what kind of video", "what is your budget"],
        "label": "Creative requirement acknowledgment",
    },
    7: {
        "check": ["5000", "Type 6", "5499", "5999", "closest"],
        "must_not": ["cannot", "not possible", "packages start from 1199"],
        "label": "Budget negotiation intelligence",
    },
    8: {
        "check": ["confirm", "today", "value", "package", "proceed"],
        "must_not": ["discount", "we cannot offer"],
        "label": "Urgency + closing trigger",
    },
    9: {
        "check": ["45", "Type 8", "9999", "upgrade", "possible"],
        "must_not": ["cannot", "not available"],
        "label": "Scope change handling",
    },
    10: {
        "check": ["payment", "milestone", "team", "arrange", "discuss"],
        "must_not": ["full payment", "we don't offer", "not possible"],
        "label": "Payment flexibility",
    },
    11: {
        "check": ["revision", "changes", "render", "rounds", "process"],
        "must_not": ["we don't", "not available"],
        "label": "Revision policy clarity",
    },
    12: {
        "check": ["festival", "deadline", "timeline", "commit", "priority"],
        "must_not": ["cannot guarantee", "we don't know"],
        "label": "Deadline commitment",
    },
    13: {
        "check": ["Type 7", "6999", "voiceover", "UGC", "separate"],
        "must_not": ["packages start from", "what type of video"],
        "label": "Package differentiation",
    },
    14: {
        "check": ["human", "team", "schedule", "call", "arrange"],
        "must_not": ["I am an AI", "I cannot connect"],
        "label": "Human escalation",
    },
    15: {
        "check": ["Type 6", "5999", "restaurant", "recommend", "package"],
        "must_not": ["what is your budget", "what type of video"],
        "label": "Final recommendation",
    },
    16: {
        "check": ["Type 6", "5999", "30", "Ultra HD", "restaurant"],
        "must_not": ["let me explain in detail", "as I mentioned"],
        "label": "4-line summary",
    },
    17: {
        "check": ["confirmed", "onboarding", "proceed", "started", "Type 6"],
        "must_not": ["what package", "please confirm"],
        "label": "Order confirmation",
    },
    18: {
        "check": ["meeting", "5 PM", "tomorrow", "calendar", "owner@myrestaurant.in"],
        "must_not": ["cannot book", "I don't have access"],
        "label": "Calendar booking",
    },
}


def run_conversation_test():
    conversation_id = None
    results = []

    print("\n" + "=" * 60)
    print("VIDIO AGENT - FULL CONVERSATION TEST")
    print("=" * 60 + "\n")

    for index, message in enumerate(TEST_MESSAGES, start=1):
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id

        label = f"Test {index}"

        try:
            response = requests.post(CHAT_ENDPOINT, json=payload, timeout=30)
            print(f"     HTTP Status : {response.status_code}")
            print(f"     Raw Response: {response.text[:200]}")
            data = response.json()

            reply = data.get("reply", "")
            conversation_id = data.get("conversation_id", conversation_id)
            stage = data.get("stage", "unknown")

            criteria = EXPECTED_BEHAVIORS.get(index, {})
            checks = criteria.get("check", [])
            must_not = criteria.get("must_not", [])
            label = criteria.get("label", f"Test {index}")

            reply_lower = reply.lower()

            passed_checks = [kw for kw in checks if kw.lower() in reply_lower]
            failed_checks = [kw for kw in checks if kw.lower() not in reply_lower]
            triggered_must_not = [kw for kw in must_not if kw.lower() in reply_lower]

            score = len(passed_checks) / len(checks) * 10 if checks else 5
            if triggered_must_not:
                score = max(0, score - (len(triggered_must_not) * 2))

            score = round(min(score, 10), 1)

            status = "PASS" if score >= 6 and not triggered_must_not else "FAIL"

            results.append(
                {
                    "index": index,
                    "label": label,
                    "score": score,
                    "status": status,
                    "passed_checks": passed_checks,
                    "failed_checks": failed_checks,
                    "triggered_must_not": triggered_must_not,
                    "reply_preview": reply[:120] if reply else "EMPTY RESPONSE",
                }
            )

            print(f"[{index:02d}] {label}")
            print(f"     Status : {status}  |  Score : {score}/10")
            print(f"     Stage  : {stage}")
            print(f"     Reply  : {reply[:100]}...")
            if failed_checks:
                print(f"     Missing: {failed_checks}")
            if triggered_must_not:
                print(f"     BAD phrases detected: {triggered_must_not}")
            print()

            time.sleep(1.5)

        except requests.exceptions.ConnectionError:
            print(f"[{index:02d}] CONNECTION ERROR - Is server running at {BASE_URL}?\n")
            results.append({"index": index, "label": label, "score": 0, "status": "ERROR"})
            break

        except Exception as e:
            print(f"[{index:02d}] ERROR: {type(e).__name__}: {str(e)}\n")
            results.append({"index": index, "label": label, "score": 0, "status": "ERROR"})

    print("=" * 60)
    print("FINAL EVALUATION REPORT")
    print("=" * 60)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    avg_score = round(sum(r["score"] for r in results) / total, 1)

    print(f"Total Tests   : {total}")
    print(f"Passed        : {passed}/{total}")
    print(f"Average Score : {avg_score}/10")
    print(
        f"Overall Grade : {'A' if avg_score >= 8 else 'B' if avg_score >= 6 else 'C' if avg_score >= 4 else 'D'}"
    )
    print()

    print("PER-TEST SUMMARY:")
    for r in results:
        bar = "█" * int(r["score"]) + "░" * (10 - int(r["score"]))
        print(f"  [{r['index']:02d}] {bar} {r['score']}/10  {r['status']}  — {r['label']}")

    print("\nTest complete.")
    print(f"Conversation ID used: {conversation_id}")


if __name__ == "__main__":
    run_conversation_test()
