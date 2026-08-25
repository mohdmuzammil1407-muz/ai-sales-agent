import os
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

from app.core.prompts import MASTER_SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "True").strip().lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def build_state_context(state) -> str:
    return f"""
Current Stage: {state.stage}
Sales Mode: {getattr(state, 'sales_mode', 'discovery')}
Name: {state.name}
Email: {state.email}
Business: {state.business_name}
Mood: {getattr(state, 'mood', None)}
Creative Direction: {getattr(state, 'creative_direction', None)}
Video Type: {state.video_type}
Target Audience: {state.target_audience}
Timeline: {state.timeline}
Budget: {state.budget}
Recommended Package: {state.recommended_package}
Lead Score: {state.lead_score}
Order Confirmed: {state.order_confirmed}
"""


def generate_response(
    user_message: str,
    state,
    retrieved_context: str = None
) -> str:

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set")
        return "Configuration error. Please contact support."

    if MOCK_MODE:
        logger.info("MOCK_MODE is ON — returning mock response")
        return _mock_response(user_message, state)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        state_context = build_state_context(state)

        system_content = MASTER_SYSTEM_PROMPT
        system_content += f"\n\n---\nCURRENT CONVERSATION STATE:\n{state_context}\n---"

        if retrieved_context:
            system_content += f"\n\nRELEVANT KNOWLEDGE BASE CONTEXT:\n{retrieved_context}\n---"

        messages = [{"role": "system", "content": system_content}]

        for msg in state.conversation_history[-10:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,
            max_tokens=500,
            stream=False,
            timeout=15
        )

        reply = response.choices[0].message.content.strip()
        logger.info(f"LLM response generated: {reply[:80]}...")
        return reply

    except Exception as e:
        logger.error(f"LLM error: {type(e).__name__}: {str(e)}")
        return "I didn't quite catch that — could you rephrase? 😊"


def _mock_response(user_message: str, state) -> str:
    msg = user_message.lower()

    # ── Consultative Mode (business query injected context) ──
    if "[consultative mode activated]" in msg:
        original = user_message
        # Extract the real user message after "User message:" tag if present
        if "user message:" in msg:
            original = user_message.split("User message:")[-1].strip()
        original_lower = original.lower()

        if any(kw in original_lower for kw in ["kitchen", "washroom", "bathroom", "home products", "household"]):
            return (
                "That's a great space to be in! Kitchen and washroom products have massive visual potential "
                "— customers often decide to buy based on how a product looks and feels before they ever touch it.\n\n"
                "Here's how we can help your brand stand out:\n\n"
                "🧴 **3D Product Animation (Type 3)** — Showcase your kitchen and bathroom items with stunning "
                "detail, highlighting materials, textures, and features. Perfect for Amazon listings, ads, and social content.\n\n"
                "📱 **UGC-Style Ads (Type 5)** — Authentic, lifestyle-feel videos showing your products in real "
                "home settings. Great for building trust and driving conversions on Instagram and Reels.\n\n"
                "Quick question — are you primarily selling online (Amazon, Shopify, Instagram) or through retail stores? "
                "That'll help me suggest the best content strategy for you! 😊"
            )

        if any(kw in original_lower for kw in ["fashion", "clothing", "apparel", "wear", "dress"]):
            return (
                "Fashion brands thrive on visual identity — the right video content can turn a scroll-stop into a sale.\n\n"
                "Here's what works best for your space:\n\n"
                "🎬 **Brand Film / Voiceover Storytelling (Type 6)** — Cinematic lookbook-style content that "
                "showcases your collection with mood and movement. Perfect for brand awareness campaigns.\n\n"
                "📱 **UGC-Style Ads (Type 5)** — Authentic, influencer-feel content that drives conversions on "
                "Instagram and TikTok. Builds social proof and feels native to the feed.\n\n"
                "What's your primary goal right now — growing brand awareness, driving direct sales, or both? 🎯"
            )

        if any(kw in original_lower for kw in ["restaurant", "cafe", "food service", "dining"]):
            return (
                "Restaurants and food businesses that invest in visual content see real results — "
                "people eat with their eyes first, and great video drives both foot traffic and delivery orders.\n\n"
                "Here's what we'd recommend for you:\n\n"
                "🍽️ **Food & Restaurant Animation (Type 4)** — Cinematic food visuals that capture texture, "
                "steam, and ambiance. Perfect for social media, delivery apps, and menu promotions.\n\n"
                "🎥 **Brand Film (Type 6)** — Tell your restaurant's story and atmosphere in a premium, "
                "cinematic way that sets you apart from the competition.\n\n"
                "Are you focused more on attracting new customers, promoting specific dishes, or building brand awareness? 🎬"
            )

        # Generic business query fallback
        return (
            "Great that you're thinking about this! Video content is one of the most powerful ways to "
            "grow a product-based business right now — it builds trust, showcases value, and drives conversions.\n\n"
            "Here's how we typically help businesses like yours:\n\n"
            "✨ **Product Animation (Type 3)** — Show your products in the best light with realistic 3D animation "
            "that highlights features and quality.\n\n"
            "📱 **UGC-Style Ads (Type 5)** — Authentic content that feels real and relatable, perfect for "
            "social media ads and building trust with new customers.\n\n"
            "What products are you looking to promote first, and where are you mainly selling — online or in stores? 😊"
        )

    # ── Standard mock responses ──
    if any(kw in msg for kw in ["restaurant", "food", "promo", "cinematic"]):
        if any(kw in msg for kw in ["days", "deadline", "10"]):
            return "That's a solid brief. A 10-day turnaround is feasible. For restaurant promos with cinematic food shots, our Type 6 package at ₹5999 is the best fit."
        return "For a restaurant promo with cinematic visuals, our Type 6 package at ₹5999 is ideal — Ultra HD, food-specific production style."

    if state.stage == "greeting":
        return "Hi, I'm Vidio. What kind of video are you looking to create?"

    if state.stage == "discovery":
        return "Got it. What's the target audience and where are you planning to use this video?"

    if state.stage == "qualification":
        missing = []
        if not state.name: missing.append("your name")
        if not state.email: missing.append("your email")
        if missing:
            return f"Almost there — could you share {' and '.join(missing)}?"
        return "Great. Based on what you've shared, shall we move forward with the recommended package?"

    if state.stage == "closing":
        return f"Your {state.recommended_package or 'Type 6'} project is confirmed. Our team will begin onboarding shortly."

    return "Could you tell me a bit more so I can point you in the right direction?"
