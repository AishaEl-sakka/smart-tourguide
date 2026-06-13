"""
Accuracy evaluation utilities.
- ROUGE score for Q&A answer quality
- Semantic similarity using sentence-transformers
- Plan structure validator (schema completeness)
- Budget accuracy checker
"""
from __future__ import annotations
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── ROUGE scoring (Q&A) ───────────────────────────────────────────────────────

def rouge_score(hypothesis: str, reference: str) -> dict[str, float]:
    """Compute ROUGE-1, ROUGE-2, ROUGE-L between hypothesis and reference."""
    try:
        from rouge_score import rouge_scorer as rs_mod
        scorer = rs_mod.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
        scores = scorer.score(reference, hypothesis)
        return {
            "rouge1_f": round(scores["rouge1"].fmeasure, 4),
            "rouge2_f": round(scores["rouge2"].fmeasure, 4),
            "rougeL_f": round(scores["rougeL"].fmeasure, 4),
        }
    except ImportError:
        logger.warning("rouge_score not installed — skipping ROUGE eval")
        return {}


# ── Semantic similarity (Q&A) ─────────────────────────────────────────────────

_embed_model = None

def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("sentence-transformers not installed — skipping semantic eval")
    return _embed_model


def semantic_similarity(text_a: str, text_b: str) -> float | None:
    """Cosine similarity between two texts using MiniLM embeddings. Range [0,1]."""
    model = _get_embed_model()
    if model is None:
        return None
    try:
        import numpy as np
        emb_a, emb_b = model.encode([text_a, text_b])
        cosine = float(np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b)))
        return round(max(0.0, cosine), 4)
    except Exception as e:
        logger.warning("Semantic similarity failed: %s", e)
        return None


# ── Q&A evaluator ─────────────────────────────────────────────────────────────

def evaluate_qa_response(
    answer: str,
    reference: str | None = None,
    *,
    min_length: int = 30,
) -> dict[str, Any]:
    """
    Evaluate a Q&A answer for quality signals.
    Returns a dict with scores and flags.
    """
    result: dict[str, Any] = {
        "length": len(answer),
        "has_min_content": len(answer) >= min_length,
        "has_hallucination_markers": any(
            phrase in answer.lower()
            for phrase in ["i don't know", "i cannot", "i'm not sure", "as an ai"]
        ),
    }

    if reference:
        result["rouge"] = rouge_score(answer, reference)
        result["semantic_similarity"] = semantic_similarity(answer, reference)

    # Overall quality flag
    result["quality"] = (
        "good"    if result["has_min_content"] and not result["has_hallucination_markers"]
        else "poor"
    )
    return result


# ── Plan schema validator ─────────────────────────────────────────────────────

REQUIRED_PLAN_KEYS = {"trip_summary", "days", "tips", "data_quality"}
REQUIRED_DAY_KEYS  = {"day", "activities", "meals", "accommodation", "day_total_cost"}
REQUIRED_SUMMARY_KEYS = {"destination", "duration_days", "total_budget", "currency",
                          "activity_type", "budget_breakdown"}


def validate_plan_schema(plan: dict) -> dict[str, Any]:
    """Check that the plan JSON has all required fields."""
    issues: list[str] = []

    missing_top = REQUIRED_PLAN_KEYS - set(plan.keys())
    if missing_top:
        issues.append(f"Missing top-level keys: {missing_top}")

    summary = plan.get("trip_summary", {})
    missing_summary = REQUIRED_SUMMARY_KEYS - set(summary.keys())
    if missing_summary:
        issues.append(f"trip_summary missing: {missing_summary}")

    days = plan.get("days", [])
    if not days:
        issues.append("No days in plan")
    else:
        for d in days:
            missing_day = REQUIRED_DAY_KEYS - set(d.keys())
            if missing_day:
                issues.append(f"Day {d.get('day','?')} missing: {missing_day}")

    return {
        "schema_valid": len(issues) == 0,
        "issues": issues,
        "num_days_in_plan": len(days),
    }


# ── Budget accuracy checker ───────────────────────────────────────────────────

def check_budget_accuracy(plan: dict) -> dict[str, Any]:
    """
    Verify that day totals sum correctly and don't exceed the overall budget.
    """
    summary   = plan.get("trip_summary", {})
    days      = plan.get("days", [])
    total_budget = summary.get("total_budget", 0) or 0

    day_totals = [d.get("day_total_cost", 0) or 0 for d in days]
    computed_total = sum(day_totals)
    breakdown = summary.get("budget_breakdown", {})
    breakdown_total = sum(v for v in breakdown.values() if isinstance(v, (int, float)))

    over_budget = computed_total > total_budget * 1.05   # 5% tolerance

    return {
        "total_budget":       total_budget,
        "computed_total":     round(computed_total, 2),
        "breakdown_total":    round(breakdown_total, 2),
        "over_budget":        over_budget,
        "variance_pct":       round(abs(computed_total - total_budget) / max(total_budget, 1) * 100, 1),
        "budget_accurate":    not over_budget,
    }


# ── Full plan evaluator ───────────────────────────────────────────────────────

def evaluate_plan(plan: dict) -> dict[str, Any]:
    """Run all plan checks and return a combined evaluation report."""
    schema  = validate_plan_schema(plan)
    budget  = check_budget_accuracy(plan) if schema["schema_valid"] else {}
    quality = plan.get("data_quality", {})

    overall = (
        "good"
        if schema["schema_valid"] and budget.get("budget_accurate", False)
        else "needs_review"
    )

    return {
        "overall": overall,
        "schema":  schema,
        "budget":  budget,
        "data_quality": quality,
    }