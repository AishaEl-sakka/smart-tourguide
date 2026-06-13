"""
Tests for the trip planning graph.
Covers: collector, budget validator, aggregator, plan schema, accuracy.
"""
import pytest
from unittest.mock import patch, AsyncMock

from app.graph.plan_graph.nodes.collector import collector_node, REQUIRED_FIELDS
from app.graph.plan_graph.nodes.budget_validator import budget_validator_node
from app.graph.plan_graph.nodes.aggregator import aggregator_node
from app.evaluation.accuracy import (
    validate_plan_schema,
    check_budget_accuracy,
    evaluate_plan,
)


# ── Collector tests ───────────────────────────────────────────────────────────

def test_collector_detects_missing_fields():
    state = {
        "session_id": "s1",
        "messages": [{"role": "user", "content": "I want to visit Egypt"}],
        "constraints": {},
    }
    with patch("app.graph.plan_graph.nodes.collector.get_llm") as mock_llm:
        mock = mock_llm.return_value
        mock.invoke.return_value.content = '{"budget": null, "currency": null, "num_days": null, "activity_type": null, "destination": "Egypt"}'
        result = collector_node(state)

    assert set(result["missing_fields"]) == {"budget", "num_days", "activity_type"}
    assert result["collector_question"] != ""


def test_collector_all_fields_present():
    state = {
        "session_id": "s2",
        "messages": [{"role": "user", "content": "600 USD, 7 days, cultural"}],
        "constraints": {},
    }
    with patch("app.graph.plan_graph.nodes.collector.get_llm") as mock_llm:
        mock = mock_llm.return_value
        mock.invoke.return_value.content = '{"budget": 600, "currency": "USD", "num_days": 7, "activity_type": "cultural", "destination": "Cairo"}'
        result = collector_node(state)

    assert result["missing_fields"] == []
    assert result["constraints"]["budget"] == 600


# ── Budget validator tests ────────────────────────────────────────────────────

def _make_state(budget, currency, num_days):
    return {
        "constraints": {"budget": budget, "currency": currency, "num_days": num_days},
    }


def test_budget_validator_valid():
    with patch("app.graph.plan_graph.nodes.budget_validator.asyncio.run") as mock_run:
        mock_run.return_value = {"rate": 1.0, "from": "USD", "to": "USD", "source": "identity"}
        result = budget_validator_node(_make_state(500, "USD", 5))
    v = result["budget_validation"]
    assert v["is_valid"] is True
    assert v["tier"] in ("budget", "mid-range", "luxury")


def test_budget_validator_too_low():
    with patch("app.graph.plan_graph.nodes.budget_validator.asyncio.run") as mock_run:
        mock_run.return_value = {"rate": 1.0, "from": "USD", "to": "USD", "source": "identity"}
        result = budget_validator_node(_make_state(10, "USD", 7))
    v = result["budget_validation"]
    assert v["is_valid"] is False
    assert "too low" in v["reason"]


def test_budget_validator_too_high():
    with patch("app.graph.plan_graph.nodes.budget_validator.asyncio.run") as mock_run:
        mock_run.return_value = {"rate": 1.0, "from": "USD", "to": "USD", "source": "identity"}
        result = budget_validator_node(_make_state(999_999, "USD", 3))
    v = result["budget_validation"]
    assert v["is_valid"] is False


# ── Schema validation tests ───────────────────────────────────────────────────

SAMPLE_PLAN = {
    "trip_summary": {
        "destination": "Cairo",
        "duration_days": 3,
        "total_budget": 600.0,
        "currency": "USD",
        "activity_type": "cultural",
        "budget_breakdown": {
            "accommodation": 180.0,
            "food": 120.0,
            "activities": 180.0,
            "transport": 60.0,
            "misc": 30.0,
        },
    },
    "days": [
        {
            "day": 1,
            "date_note": "Day 1 - Arrival & Pyramids",
            "weather_note": "Sunny, 32°C",
            "accommodation": {"name": "Cairo Budget Hotel", "area": "Giza", "estimated_cost": 60.0},
            "activities": [
                {"time": "09:00", "name": "Great Pyramid", "type": "cultural",
                 "duration_minutes": 180, "cost": 20.0, "notes": "Book early",
                 "travel_to_next_minutes": 30},
            ],
            "meals": {
                "breakfast": {"suggestion": "Hotel breakfast", "estimated_cost": 5.0},
                "lunch": {"suggestion": "Local koshary", "estimated_cost": 3.0},
                "dinner": {"suggestion": "Restaurant near Sphinx", "estimated_cost": 15.0},
            },
            "day_total_cost": 190.0,
        },
        {
            "day": 2, "date_note": "Day 2 - Museum", "weather_note": "Clear",
            "accommodation": {"name": "Same hotel", "area": "Giza", "estimated_cost": 60.0},
            "activities": [{"time": "10:00", "name": "Egyptian Museum", "type": "cultural",
                             "duration_minutes": 240, "cost": 15.0, "notes": "", "travel_to_next_minutes": 20}],
            "meals": {"breakfast": {"suggestion": "Café", "estimated_cost": 6.0},
                      "lunch": {"suggestion": "Street food", "estimated_cost": 4.0},
                      "dinner": {"suggestion": "Nile restaurant", "estimated_cost": 20.0}},
            "day_total_cost": 195.0,
        },
        {
            "day": 3, "date_note": "Day 3 - Departure", "weather_note": "Cloudy",
            "accommodation": {"name": "Same hotel", "area": "Giza", "estimated_cost": 60.0},
            "activities": [{"time": "10:00", "name": "Khan el-Khalili", "type": "cultural",
                             "duration_minutes": 120, "cost": 0.0, "notes": "Free entry", "travel_to_next_minutes": 0}],
            "meals": {"breakfast": {"suggestion": "Hotel", "estimated_cost": 5.0},
                      "lunch": {"suggestion": "Quick bite", "estimated_cost": 8.0},
                      "dinner": {"suggestion": "Airport", "estimated_cost": 12.0}},
            "day_total_cost": 140.0,
        },
    ],
    "tips": ["Dress modestly", "Bargain at markets", "Carry cash"],
    "data_quality": {
        "sources_used": ["nominatim", "open-meteo", "opentripmap"],
        "estimated_fields": [],
        "confidence": "high",
    },
}


def test_plan_schema_valid():
    result = validate_plan_schema(SAMPLE_PLAN)
    assert result["schema_valid"] is True
    assert result["num_days_in_plan"] == 3


def test_plan_schema_missing_key():
    bad_plan = {k: v for k, v in SAMPLE_PLAN.items() if k != "tips"}
    result = validate_plan_schema(bad_plan)
    assert result["schema_valid"] is False


def test_budget_accuracy_within_tolerance():
    result = check_budget_accuracy(SAMPLE_PLAN)
    # Day totals: 190 + 195 + 140 = 525, budget = 600 → under budget
    assert result["budget_accurate"] is True
    assert result["computed_total"] == 525.0


def test_budget_accuracy_over_budget():
    over = {
        **SAMPLE_PLAN,
        "days": [{**d, "day_total_cost": 300.0} for d in SAMPLE_PLAN["days"]],
    }
    result = check_budget_accuracy(over)
    assert result["computed_total"] == 900.0
    assert result["over_budget"] is True


def test_evaluate_plan_good():
    result = evaluate_plan(SAMPLE_PLAN)
    assert result["overall"] == "good"
    assert result["schema"]["schema_valid"] is True


def test_evaluate_plan_bad_schema():
    result = evaluate_plan({})
    assert result["overall"] == "needs_review"