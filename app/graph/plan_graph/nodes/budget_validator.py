"""
Budget validation node — validates budget and converts currency to USD.
Async version compatible with LangGraph ainvoke().
"""
from __future__ import annotations
import logging

from app.graph.plan_graph.state import PlanState, BudgetValidation
from app.graph.plan_graph.nodes.parallel.exchange import get_exchange_rate

logger = logging.getLogger(__name__)

MIN_DAILY_USD = 30.0
MAX_TOTAL_USD = 50_000.0

TIER_THRESHOLDS_DAILY = {
    "budget": (0, 80),
    "mid-range": (80, 250),
    "luxury": (250, float("inf")),
}


def _classify_tier(daily_usd: float) -> str:
    for tier, (low, high) in TIER_THRESHOLDS_DAILY.items():
        if low <= daily_usd < high:
            return tier
    return "luxury"


async def budget_validator_node(state: PlanState) -> PlanState:
    """
    Validate budget and convert to USD using real exchange API.
    """

    constraints = state.get("constraints", {})

    budget = constraints.get("budget", 0) or 0
    currency = constraints.get("currency", "USD") or "USD"
    num_days = constraints.get("num_days", 1) or 1

    try:
        budget = float(budget)
    except Exception:
        budget = 0.0

    try:
        if currency.upper() == "USD":
            budget_usd = budget
        else:
            result = await get_exchange_rate(currency, "USD")
            budget_usd = budget * float(result.get("rate", 1.0))

    except Exception as e:
        logger.warning(
            "Currency conversion failed: %s — assuming budget already USD",
            e,
        )
        budget_usd = budget

    daily_usd = budget_usd / max(num_days, 1)

    if budget_usd < MIN_DAILY_USD * num_days:

        validation = BudgetValidation(
            is_valid=False,
            reason=(
                f"Your budget of {budget} {currency} "
                f"(~${budget_usd:.0f} USD) is too low "
                f"for {num_days} days in Egypt."
            ),
            budget_usd=budget_usd,
            tier="insufficient",
            daily_budget_usd=daily_usd,
        )

    elif budget_usd > MAX_TOTAL_USD:

        validation = BudgetValidation(
            is_valid=False,
            reason=(
                f"Budget of {budget} {currency} "
                f"(~${budget_usd:.0f} USD) seems unusually high."
            ),
            budget_usd=budget_usd,
            tier="luxury",
            daily_budget_usd=daily_usd,
        )

    else:

        tier = _classify_tier(daily_usd)

        validation = BudgetValidation(
            is_valid=True,
            reason="",
            budget_usd=budget_usd,
            tier=tier,
            daily_budget_usd=daily_usd,
        )

    return {
        **state,
        "budget_validation": validation,
    }


def should_proceed_after_validation(state: PlanState) -> str:
    validation = state.get("budget_validation", {})

    if not validation.get("is_valid", False):
        return "invalid_budget"

    return "fetch_data"