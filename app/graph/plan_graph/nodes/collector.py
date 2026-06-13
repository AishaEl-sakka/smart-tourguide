"""
Information collector node — multi-turn, uses LLM to extract constraints
from user messages. Flexible fault-tolerant approach:
- REQUIRES: budget + num_days
- OPTIONAL: activity_type (defaults to "mixed")
- System proceeds even with missing optional fields
"""
from __future__ import annotations
import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_llm
from app.prompts.collector import EXTRACTION_SYSTEM_PROMPT, build_question
from app.graph.plan_graph.state import PlanState, TripConstraints

logger = logging.getLogger(__name__)

# Critical fields needed for a valid plan
REQUIRED_FIELDS = ["budget", "num_days"]
# Optional but useful for better personalization
PREFERRED_FIELDS = ["activity_type"]


def _extract_constraints(user_message: str, existing: TripConstraints) -> TripConstraints:
    """Call LLM to extract structured fields from user message."""
    llm = get_llm(temperature=0.0)
    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]
    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        # Strip markdown fences if any
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        extracted: dict = json.loads(raw)
    except Exception as e:
        logger.warning("Constraint extraction failed: %s", e)
        extracted = {}

    # Merge with existing — only update non-null newly extracted fields
    merged = dict(existing)
    for field in ["budget", "currency", "num_days", "activity_type", "destination"]:
        val = extracted.get(field)
        if val is not None:
            merged[field] = val

    # Ensure activity_type defaults to "mixed" if still missing
    if not merged.get("activity_type"):
        merged["activity_type"] = "mixed"

    return TripConstraints(**merged)


def collector_node(state: PlanState) -> PlanState:
    """
    Extract constraints from the latest user message.
    Check for critical required fields; optional fields get sensible defaults.
    """
    messages = state.get("messages", [])
    existing = state.get("constraints", TripConstraints())

    # Get the latest user turn
    user_turns = [m for m in messages if m.get("role") == "user"]
    latest_message = user_turns[-1]["content"] if user_turns else ""

    updated = _extract_constraints(latest_message, existing)

    # Set sensible defaults for everything
    if not updated.get("destination"):
        updated["destination"] = "Egypt"
    if not updated.get("currency"):
        updated["currency"] = "USD"
    if not updated.get("activity_type"):
        updated["activity_type"] = "mixed"

    # Only check for REQUIRED fields (budget, num_days)
    missing_required = [f for f in REQUIRED_FIELDS if not updated.get(f)]
    
    # Check for preferred but optional fields
    missing_preferred = [f for f in PREFERRED_FIELDS if not updated.get(f)]
    
    # Determine what to ask for
    if missing_required:
        # Critical fields are missing — ask for them
        question = build_question(missing_required)
        missing_fields = missing_required
    elif missing_preferred and state.get("first_pass", True):
        # Optional fields are missing and it's the first pass
        # Ask if user wants to specify activity type or continue with default
        question = (
            "Great! I have your budget and duration. "
            "To personalize better, what's your travel vibe?\n"
            "• **Cultural** — temples, pyramids, museums\n"
            "• **Adventure** — desert, diving, hiking\n"
            "• **Relaxed** — beach, cruise, spa\n"
            "• **Mixed** — a bit of everything (default)\n\n"
            "Or just say 'mixed' to proceed with default!"
        )
        missing_fields = missing_preferred
    else:
        # All critical fields present and user has answered about preferences
        question = ""
        missing_fields = []

    return {
        **state,
        "constraints": updated,
        "missing_fields": missing_fields,
        "collector_question": question,
        "first_pass": False,  # Mark that we've made the first pass
    }


def should_continue_collecting(state: PlanState) -> str:
    """Conditional edge: keep collecting or proceed to validation."""
    if state.get("missing_fields"):
        return "ask_user"
    return "validate_budget"