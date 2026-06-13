EXTRACTION_SYSTEM_PROMPT = """You are a travel data extractor. Extract travel planning fields from user messages.
Return ONLY a valid JSON object. No markdown, no explanation.

Fields to extract (set null if absolutely not mentioned):
- budget: number only (e.g. 500)
- currency: ISO-4217 code (e.g. "USD", "EUR", "EGP", "GBP", "SAR")
- num_days: integer (also accept "1 week" → 7, "2 weeks" → 14, etc.)
- activity_type: one of "cultural" | "adventure" | "relaxed" | "mixed"
- destination: Egyptian city/region string (e.g. "Cairo", "Luxor", "Aswan")

PARSING RULES:
1. Budget: Accept formats like "800 USD", "$800", "800", "eight hundred"
2. Duration: Accept "7 days", "1 week", "a week", "7-day" — convert to integer
3. Activity inference (BEST EFFORT):
   cultural  → history, museums, temples, pyramids, monuments, ancient, heritage
   adventure → desert, diving, snorkeling, safari, hiking, extreme, adventure sports
   relaxed   → beach, cruise, spa, resort, shopping, chill, relax
   mixed     → combination or unspecified or generic "trip"
4. Destination: Accept "Cairo", "Luxor", "Giza", "Aswan", "Red Sea", "Sinai", or just "Egypt"

IMPORTANT DEFAULTS:
- If activity_type cannot be determined, set to "mixed" (NOT null)
- If destination is missing, set to null (system will default to Egypt later)
- If currency is missing, infer from context or set to null (system defaults to USD)

EXAMPLES:
"Plan me a 7-day trip to Cairo with 800 USD"
→ {"budget": 800, "currency": "USD", "num_days": 7, "activity_type": "mixed", "destination": "Cairo"}

"I want to visit Luxor for a week, $1500, adventure activities"
→ {"budget": 1500, "currency": "USD", "num_days": 7, "activity_type": "adventure", "destination": "Luxor"}

"3 days, 300 EGP, relax at beach"
→ {"budget": 300, "currency": "EGP", "num_days": 3, "activity_type": "relaxed", "destination": null}
"""

QUESTION_MAP = {
    # Critical fields missing
    frozenset(["budget", "num_days"]): (
        "Welcome! To design your perfect Egypt trip I need:\n"
        "1. **Budget** — total amount + currency (e.g. '700 USD' or '500 EUR')\n"
        "2. **Duration** — how many days? (e.g. '7 days' or '1 week')\n\n"
        "Type both answers at once!"
    ),
    frozenset(["budget"]): (
        "Almost there! What's your **total budget** + currency?\n"
        "Examples: '600 USD', '500 EUR', '3000 EGP'"
    ),
    frozenset(["num_days"]): (
        "Almost there! How many **days** will you spend in Egypt?"
    ),
    frozenset(["budget", "num_days"]): (
        "Still need two things:\n"
        "1. Your **total budget** (e.g. '600 USD')\n"
        "2. **How many days** (e.g. '7')"
    ),
    # Optional fields missing (only ask on first pass)
    frozenset(["activity_type"]): (
        "Perfect! Now, what's your travel vibe?\n"
        "• **Cultural** — temples, pyramids, museums\n"
        "• **Adventure** — desert, diving, hiking\n"
        "• **Relaxed** — beach, cruise, spa\n"
        "• **Mixed** — a bit of everything\n\n"
        "Or just say 'mixed' to proceed!"
    ),
}


def build_question(missing: list[str]) -> str:
    key = frozenset(missing)
    return QUESTION_MAP.get(key, QUESTION_MAP[frozenset(["budget", "num_days"])])