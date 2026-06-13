"""
Top-level orchestrator — classifies intent and dispatches to the correct graph.
Not a LangGraph graph itself; it's a lightweight Python router so each subgraph
remains fully independent with its own state.
"""
from __future__ import annotations
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_llm

logger = logging.getLogger(__name__)

INTENT_PROMPT = """You are an intent classifier for an Egypt tourism assistant.
Classify the user's message into exactly one of these two intents:

- "qa"   : The user asks a question about Egypt (history, sites, culture,
            practical tips, recommendations, or general tourism info)
- "plan" : The user wants to plan or customize a trip (mentions budget,
            days, itinerary, schedule, trip planning, or booking)

Respond with ONLY the word "qa" or "plan". Nothing else.
"""


def classify_intent(message: str) -> str:
    """Classify message as 'qa' or 'plan' using LLM."""
    llm = get_llm(temperature=0.0)
    resp = llm.invoke([
        SystemMessage(content=INTENT_PROMPT),
        HumanMessage(content=message),
    ])
    intent = resp.content.strip().lower()
    if intent not in ("qa", "plan"):
        logger.warning("Unexpected intent '%s', defaulting to 'qa'", intent)
        return "qa"
    return intent


def route(message: str, session_id: str) -> tuple[str, str]:
    """
    Classify and return (intent, session_id).
    Caller uses intent to invoke the right graph.
    """
    intent = classify_intent(message)
    logger.info("session=%s | intent=%s | msg_preview=%s", session_id, intent, message[:60])
    return intent, session_id