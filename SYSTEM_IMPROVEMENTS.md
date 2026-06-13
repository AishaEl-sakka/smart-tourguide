# System Improvements: Flexible & Fault-Tolerant Trip Planning

## Problem
The API was returning **500 error: "Aggregated context missing — cannot plan"** when users sent generic requests like:
> "Plan me a 7-day trip to Cairo with 800 USD"

**Root cause:** The system required **3 critical fields**:
- `budget` ✓ (provided: 800 USD)
- `num_days` ✓ (provided: 7 days)  
- `activity_type` ✗ (not specified — defaults to null)

When `activity_type` was missing, the collector would ask a follow-up question, but the user had to respond before proceeding to planning. This broke the user experience.

---

## Solution: Flexible & Fault-Tolerant Design

### Key Changes

#### 1. **Categorize Fields into Tiers**
| Tier | Fields | Behavior |
|------|--------|----------|
| **REQUIRED** | `budget`, `num_days` | Must be present to proceed to planning |
| **OPTIONAL** | `activity_type` | Defaults to `"mixed"` if missing; asked on first pass |
| **AUTO-DEFAULT** | `destination`, `currency` | Defaults applied automatically |

#### 2. **More Flexible Extraction Prompt**
- Improved parsing of common input formats
  - `"800 USD"`, `"$800"`, `"800"` → all recognized as budget 800 USD
  - `"7 days"`, `"1 week"`, `"7-day trip"` → all converted to 7 days
  - `"cultural"`, `"history"`, `"temples"` → inferred as `activity_type="cultural"`

- **Default behavior**: If `activity_type` can't be inferred, set to `"mixed"` (not null)

#### 3. **Progressive Information Collection**
**Flow:**
1. **First turn**: Extract all available info, default missing optional fields
2. **If critical fields missing**: Ask for them ❌ → User must answer
3. **If only optional fields missing**: Offer personalization question ⚠️ → User can skip
4. **Once critical fields present**: Proceed to planning ✅

#### 4. **Improved User Prompts**
- Clearer distinction between "critical" and "nice-to-have" fields
- Option to proceed with defaults (e.g., "Or just say 'mixed' to proceed!")
- Example-driven guidance for ambiguous inputs

---

## Technical Changes

### File: `app/prompts/collector.py`
```python
# Enhanced extraction prompt with:
- Parsing rules for common input formats
- Activity type inference guidelines
- Explicit default behavior (activity_type defaults to "mixed", not null)

# Simplified question map:
- Only asks for REQUIRED fields first
- Then optionally asks for PREFERRED fields if first pass
```

### File: `app/graph/plan_graph/nodes/collector.py`
```python
# Changed field categorization:
REQUIRED_FIELDS = ["budget", "num_days"]        # Critical
PREFERRED_FIELDS = ["activity_type"]             # Optional but nice

# Improved extraction with automatic defaults:
- activity_type defaults to "mixed" if not specified
- destination defaults to "Egypt" if not specified
- currency defaults to "USD" if not specified

# Smart question logic:
- Asks for missing REQUIRED fields
- Asks for missing PREFERRED fields on first pass only
- Proceeds to planning once all REQUIRED fields present
```

---

## User Experience Improvements

### Before
```
USER: Plan me a 7-day trip to Cairo with 800 USD

SYSTEM: ❌ 500 Error: Aggregated context missing — cannot plan
```

### After
```
USER: Plan me a 7-day trip to Cairo with 800 USD

SYSTEM: ✅
Perfect! Now, what's your travel vibe?
• Cultural — temples, pyramids, museums
• Adventure — desert, diving, hiking  
• Relaxed — beach, cruise, spa
• Mixed — a bit of everything

Or just say 'mixed' to proceed!

---

USER: mixed

SYSTEM: ✅ Planning your 7-day trip to Cairo with $800 budget...
[Generates complete itinerary with mixed activities]
```

### Additional Scenarios Now Supported

**Scenario 1: Minimal input**
```
USER: 7 days, 500 USD
SYSTEM: ✅ Proceeds with defaults (Cairo, mixed activities, USD)
```

**Scenario 2: Different currency**
```
USER: 10 days, 2000 EUR, adventure trip
SYSTEM: ✅ Converts EUR to USD, plans adventure activities
```

**Scenario 3: Specific destination + activity**
```
USER: 3 days in Luxor, cultural activities, 600 USD
SYSTEM: ✅ Immediately proceeds to planning (all info provided)
```

---

## Backward Compatibility
✅ **Fully backward compatible** — existing API contracts unchanged

- Endpoint `/plan` behavior same
- Response format unchanged
- Rate limits unchanged
- All new logic is internal to the collector node

---

## Testing
Run comprehensive tests:
```bash
python test_fix.py
```

Expected output: All test cases pass, demonstrating:
1. Extraction of partial information
2. Proper defaulting of optional fields
3. Correct conditional flow
4. Appropriate follow-up questions

---

## Summary
The system is now **more resilient** to incomplete user input while remaining **easy to use**:
- ✅ Handles generic requests gracefully
- ✅ Provides sensible defaults
- ✅ Still asks for personalization when helpful
- ✅ Never blocks planning unnecessarily
- ✅ Clear, user-friendly prompts
