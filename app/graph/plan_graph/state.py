"""
TypedDict state for the trip planning graph.
Each field maps to a stage of the pipeline.
"""
from __future__ import annotations
from typing import Any, Optional
from typing_extensions import TypedDict


class TripConstraints(TypedDict, total=False):
    budget: Optional[float]
    currency: Optional[str]
    num_days: Optional[int]
    activity_type: Optional[str]
    destination: Optional[str]


class BudgetValidation(TypedDict):
    is_valid: bool
    reason: str                  # empty string when valid
    budget_usd: float            # converted to USD for comparison
    tier: str                    # "budget" | "mid-range" | "luxury"
    daily_budget_usd: float


class ParallelData(TypedDict, total=False):
    geocode: dict
    weather: dict
    activities: dict
    hotels: dict
    routing: dict
    exchange: dict


class PlanState(TypedDict, total=False):
    # Input
    session_id: str
    messages: list[dict]

    # Collector stage
    constraints: TripConstraints
    missing_fields: list[str]
    collector_question: str

    # Validation stage
    budget_validation: BudgetValidation

    # Parallel data stage
    parallel_data: ParallelData

    # Aggregator stage
    aggregated_context: dict

    # Output stage
    plan_json: dict
    error: Optional[str]