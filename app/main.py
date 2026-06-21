"""
FastAPI application — Egypt Tourism Multi-Agent System
Endpoints:
  GET  /health         — liveness check
  POST /chat           — Q&A agent
  POST /plan           — Trip planning agent (multi-turn)
  GET  /plan/{session} — Retrieve plan state for a session
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from logging import config, error
from typing import Any
from unittest import result

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.config import get_settings, get_llm
from app.schemas import (
    ChatRequest, ChatResponse,
    PlanRequest, PlanCompleteResponse, PlanQuestionResponse,
    HealthResponse,
)
from app.middleware.logging import configure_logging, RequestLoggingMiddleware
from app.middleware.rate_limit import limiter
from app.graph.orchestrator import route
from app.graph.qa_graph.graph import qa_graph
from app.graph.plan_graph.graph import plan_graph
from app.evaluation.accuracy import evaluate_qa_response, evaluate_plan

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    logger.info("Egypt Tourism Agent starting | env=%s", s.app_env)

    # Validate at least one LLM is configured
    try:
        get_llm()
        logger.info("LLM provider ready")
    except RuntimeError as e:
        logger.error("LLM not configured: %s", e)

    yield
    logger.info("Egypt Tourism Agent shutting down")


app = FastAPI(
    title="Egypt Tourism Multi-Agent API",
    description="Q&A and trip planning powered by LangGraph + free APIs",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    s = get_settings()
    provider = "groq" if s.groq_api_key else ("gemini" if s.google_api_key else "none")
    return HealthResponse(status="ok", llm_provider=provider, env=s.app_env)


# ── Q&A endpoint ──────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse, tags=["Q&A"])
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatRequest):
    """
    Ask any Egypt tourism question.
    Returns a direct answer with optional accuracy evaluation.
    """
    intent, session_id = route(body.message, body.session_id)

    # If user accidentally sends a planning request here, redirect intent
    if intent == "plan":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "This looks like a trip planning request. Please use POST /plan instead.",
                "session_id": session_id,
            },
        )

    config = {"configurable": {"thread_id": session_id}}
    state_in = {
        "session_id": session_id,
        "messages": [{"role": "user", "content": body.message}],
    }

    try:
        result = qa_graph.invoke(state_in, config=config)
    except Exception as e:
        logger.error("QA graph error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    answer = result.get("answer", "I could not generate an answer.")
    evaluation = evaluate_qa_response(answer)

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        evaluation=evaluation,
    )


# ── Planning endpoint ─────────────────────────────────────────────────────────
@app.post("/plan", tags=["Planning"])
@limiter.limit("10/minute")
async def plan(request: Request, body: PlanRequest):
    """
    Multi-turn trip planning endpoint.

    Continues an existing session if session_id is provided.
    Returns either a follow-up question (type='question')
    or the full itinerary JSON (type='plan').
    """
    session_id = body.session_id
    config = {"configurable": {"thread_id": session_id}}

    # Get existing state if session exists
    try:
        existing = plan_graph.get_state(config)
        current_values: dict[str, Any] = existing.values if existing else {}
    except Exception:
        current_values = {}

    # Append new user message to history
    history = current_values.get("messages", [])
    history = history + [{"role": "user", "content": body.message}]

    state_in = {
        **current_values,
        "session_id": session_id,
        "messages": history,
    }

    try:
        result = await plan_graph.ainvoke(
            state_in,
            config=config,
)

    except Exception as e:
        import traceback

        print("\n" + "=" * 80)
        print("PLAN GRAPH ERROR")
        traceback.print_exc()
        print("=" * 80 + "\n")

        logger.exception("Plan graph error")

        raise HTTPException(
        status_code=500,
        detail=str(e),
        )
    # ── Determine response type ───────────────────────────────────────────────
    missing = result.get("missing_fields", [])
    question = result.get("collector_question", "")
    plan_json = result.get("plan_json")
    error = result.get("error")

    print("\nRESULT KEYS:", result.keys())
    print("PLAN ERROR:", error)
    print("PLAN JSON EXISTS:", bool(result.get("plan_json")))
    print()

    if error:
        raise HTTPException(
            status_code=500,
            detail=error
        )
    if plan_json:
        eval_result = evaluate_plan(plan_json)
        return PlanCompleteResponse(
            session_id=session_id,
            plan=plan_json,
            evaluation=eval_result,
        )

    if missing or question:
        return PlanQuestionResponse(
            session_id=session_id,
            message=question or "Please provide more details.",
            collected_so_far={
                k: v for k, v in result.get("constraints", {}).items()
                if v is not None
            },
        )

    # Fallback
    raise HTTPException(status_code=500, detail="Unexpected graph state")


# ── Session state retrieval ───────────────────────────────────────────────────
@app.get("/plan/{session_id}", tags=["Planning"])
async def get_plan_state(session_id: str):
    """Retrieve current planning session state (for debugging / resume)."""
    config = {"configurable": {"thread_id": session_id}}
    try:
        state = plan_graph.get_state(config)
        if not state or not state.values:
            raise HTTPException(status_code=404, detail="Session not found")
        values = state.values
        return {
            "session_id": session_id,
            "constraints": values.get("constraints", {}),
            "missing_fields": values.get("missing_fields", []),
            "budget_validation": values.get("budget_validation", {}),
            "has_plan": bool(values.get("plan_json")),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))