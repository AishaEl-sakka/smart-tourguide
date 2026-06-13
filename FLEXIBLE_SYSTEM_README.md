# Flexible & Fault-Tolerant Trip Planning System

## Overview
The system has been upgraded to handle user requests gracefully, with intelligent defaults and progressive information gathering.

---

## Key Features

### 🎯 Smart Defaults
- **`activity_type`** → defaults to `"mixed"` if not specified
- **`destination`** → defaults to `"Egypt"` if not specified  
- **`currency`** → defaults to `"USD"` if not specified

### 💪 Fault Tolerance
- System continues even if optional info is missing
- Only blocks when **critical** information is absent:
  - ✅ `budget` — required
  - ✅ `num_days` — required
  - 📝 `activity_type` — optional (has default)

### 🤝 Progressive Collection
1. **Extract** all available info from initial request
2. **Fill in** defaults for missing optional fields
3. **Ask** for critical fields if missing
4. **Offer** personalization if first interaction
5. **Proceed** to planning once ready

### 🧠 Intelligent Parsing
Extracts information from various input formats:
```
"7-day trip to Cairo with 800 USD"          ✅
"Cairo, 7 days, $800"                        ✅
"I want to spend 800 USD over 7 days"        ✅
"800 USD for a week in Cairo"                ✅
```

---

## Field Requirements

| Field | Required? | Type | Default | Example |
|-------|-----------|------|---------|---------|
| `budget` | ✅ YES | float | — | 800 |
| `num_days` | ✅ YES | int | — | 7 |
| `activity_type` | ❌ NO | string | "mixed" | "cultural" |
| `destination` | ❌ NO | string | "Egypt" | "Cairo" |
| `currency` | ❌ NO | string | "USD" | "USD" |

**Definition:**
- **Required:** Blocks planning if missing — must be provided
- **Optional:** Has sensible default — system proceeds automatically

---

## Usage Examples

### Example 1: Minimal Valid Input ✅
```
USER: "7 days, 500 USD"

SYSTEM PROCESSING:
├─ Extracted: budget=500, num_days=7
├─ Defaults: destination="Egypt", activity_type="mixed", currency="USD"
└─ Status: Ready to proceed ✅

RESULT: Creates plan for 7-day mixed activities in Egypt with $500 budget
```

### Example 2: Generic Request ✅ (Original Issue - Now Fixed!)
```
USER: "Plan me a 7-day trip to Cairo with 800 USD"

SYSTEM PROCESSING:
├─ Extracted: budget=800, num_days=7, destination="Cairo"
├─ Defaults: activity_type="mixed", currency="USD"
└─ Status: Ready to proceed ✅

RESULT: Creates plan for 7-day mixed activities in Cairo with $800 budget

BEFORE FIX: ❌ 500 Error
AFTER FIX:  ✅ Success!
```

### Example 3: Partial Info (Critical Field Missing) ❌→✅
```
USER: "3 days in Luxor with adventure activities"

SYSTEM PROCESSING:
├─ Extracted: destination="Luxor", num_days=3, activity_type="adventure"
├─ Missing: budget (REQUIRED)
└─ Status: Blocked — ask for budget ❌

SYSTEM: "Almost there! What's your budget + currency? (e.g. '600 USD')"

USER: "600 USD"

SYSTEM:
├─ Updated: budget=600
└─ Status: Ready to proceed ✅

RESULT: Creates plan for 3-day adventure in Luxor with $600 budget
```

### Example 4: With Personalization ✅
```
USER: "Plan 5 days in Giza with 400 USD"

SYSTEM PROCESSING:
├─ Extracted: destination="Giza", num_days=5, budget=400
├─ Defaults: activity_type="mixed", currency="USD"
├─ Status: Ready to proceed ✅
└─ Optional: "What's your travel vibe?" (user can customize)

USER: "cultural"

UPDATED:
├─ activity_type → "cultural"
└─ Status: Ready to proceed with cultural focus ✅

RESULT: Creates plan for 5-day cultural activities in Giza with $400 budget
```

### Example 5: Multiple Missing Fields ❌
```
USER: "I want to travel"

SYSTEM PROCESSING:
├─ Missing: budget, num_days (both REQUIRED)
├─ Status: Blocked — ask for critical info ❌

SYSTEM: "To design your perfect Egypt trip I need:
1. Budget — total amount + currency (e.g. '700 USD')
2. Duration — how many days? (e.g. '7 days')

Type both answers at once!"

USER: "1000 USD for 10 days"

RESULT: Plan created ✅
```

---

## API Usage

### Request
```bash
curl -X POST http://127.0.0.1:8000/plan \
  -H "Content-Type: application/json" \
  -d {
    "message": "Plan me a 7-day trip to Cairo with 800 USD",
    "session_id": "user-123"
  }
```

### Response - When Ready to Plan ✅
```json
{
  "session_id": "user-123",
  "plan": {
    "destination": "Cairo",
    "num_days": 7,
    "budget": 800,
    "currency": "USD",
    "daily_budget": 114.29,
    "days": [
      {
        "day": 1,
        "title": "Arrival & Giza Pyramids",
        "activities": [...],
        "estimated_cost": 100
      },
      ...
    ],
    "data_quality": {
      "confidence": "medium",
      "sources_used": [...],
      "estimated_fields": [...]
    }
  },
  "evaluation": {...}
}
```

### Response - When Asking for Info ⚠️
```json
{
  "session_id": "user-123",
  "message": "Almost there! What's your budget + currency?\nExamples: '600 USD', '500 EUR', '3000 EGP'",
  "collected_so_far": {
    "num_days": 7,
    "destination": "Cairo"
  }
}
```

### Response - When Offering Personalization (Optional) 📝
```json
{
  "session_id": "user-123",
  "message": "Great! I have your budget and duration. To personalize better, what's your travel vibe?\n• Cultural — temples, pyramids, museums\n• Adventure — desert, diving, hiking\n• Relaxed — beach, cruise, spa\n• Mixed — a bit of everything (default)\n\nOr just say 'mixed' to proceed with default!",
  "collected_so_far": {
    "budget": 800,
    "num_days": 7
  }
}
```

---

## System Architecture

### Before (Strict)
```
USER INPUT
    ↓
[Collector] Extract constraints
    ↓
Required: budget, num_days, activity_type
    ↓
IF ANY MISSING → ASK USER
    ↓
Block until ALL collected
```

### After (Flexible) ✅
```
USER INPUT
    ↓
[Collector] Extract constraints
    ↓
Apply defaults:
├─ activity_type → "mixed"
├─ destination → "Egypt"
└─ currency → "USD"
    ↓
Check REQUIRED: budget, num_days
    ├─ IF MISSING → Ask for them ❌
    └─ IF PRESENT → Check if want to customize ✅
    ↓
Proceed to planning
```

---

## Configuration & Defaults

Edit in `app/graph/plan_graph/nodes/collector.py`:

```python
# Required fields (system blocks without these)
REQUIRED_FIELDS = ["budget", "num_days"]

# Optional fields (system continues even without these)
PREFERRED_FIELDS = ["activity_type"]
```

Edit in `app/prompts/collector.py`:

```python
# Activity type inference and defaults
# Modify parsing rules to accept new formats
# Modify questions to change prompts
```

---

## Testing

Run comprehensive test suite:
```bash
python test_fix.py
```

Expected output: All test cases pass, demonstrating:
- ✅ Extraction of partial information
- ✅ Proper defaulting of optional fields
- ✅ Correct conditional flow
- ✅ Appropriate follow-up questions
- ✅ Graceful handling of edge cases

---

## Troubleshooting

### "I'm still getting 500 errors"
- Check LLM configuration (GROQ/Gemini API keys)
- Verify extraction prompt hasn't been corrupted
- Check parallel data fetch (geocoding, weather, hotels)

### "The system is asking too many questions"
- User might be missing budget or num_days
- System is working correctly — these are critical
- Edit QUESTION_MAP in collector.py to change wording

### "I want to change the default activity type"
- Edit line 54 in `collector.py`: `"mixed"` → your preference
- Or modify extraction prompt to infer differently

### "The system isn't extracting my input"
- Check EXTRACTION_SYSTEM_PROMPT in `collector.py`
- Ensure budget and num_days are clearly stated
- Try different format: "800 USD", "$800", "800 dollars"

---

## Contributing

To extend the system:

1. **Add new field type:**
   - Add to EXTRACTION_SYSTEM_PROMPT
   - Update TripConstraints TypedDict
   - Handle in _extract_constraints()
   - Add to build_question() if user-facing

2. **Change defaults:**
   - Edit lines 74-79 in collector.py

3. **Modify questions:**
   - Edit QUESTION_MAP in collector.py

4. **Test changes:**
   - Update test_fix.py
   - Run: `python test_fix.py`

---

## Version History

### v2.0 (Current) — Flexible & Fault-Tolerant
- ✅ Optional activity_type field
- ✅ Intelligent defaults
- ✅ Smart conditional flow
- ✅ Better extraction parsing
- ✅ Improved user prompts

### v1.0 (Previous) — Strict Requirement
- ⚠️ All 3 fields required
- ⚠️ Blocks on any missing field
- ⚠️ Generic extraction
- ❌ 500 errors on incomplete input

---

## Support

- 📖 See [SYSTEM_IMPROVEMENTS.md](./SYSTEM_IMPROVEMENTS.md) for detailed explanation
- 📋 See [CHANGES_SUMMARY.md](./CHANGES_SUMMARY.md) for before/after
- 🧪 Run [test_fix.py](./test_fix.py) to verify behavior
- ✅ See [FIX_VERIFICATION.md](./FIX_VERIFICATION.md) for technical details
