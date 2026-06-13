"""
Budget validation node — converts currency to USD, checks feasibility,
classifies tier, and rejects clearly impossible budgets before API calls.
"""
from __future__ import annotations
import asyncio
import logging

from app.config import get_settings
from app.graph.plan_graph.state import PlanState, BudgetValidation
from app.graph.plan_graph.nodes.parallel.exchange import get_exchange_rate

logger = logging.getLogger(__name__)

# Minimum viable daily budget in USD (covers basic hostel + food + 1 site)
MIN_DAILY_USD = 30.0
# Maximum we'll trust (above this is likely a data error)
MAX_TOTAL_USD = 50_000.0

TIER_THRESHOLDS_DAILY = {
    "budget":    (0, 80),
    "mid-range": (80, 250),
    "luxury":    (250, float("inf")),
}


def _classify_tier(daily_usd: float) -> str:
    for tier, (low, high) in TIER_THRESHOLDS_DAILY.items():
        if low <= daily_usd < high:
            return tier
    return "luxury"


def budget_validator_node(state: PlanState) -> PlanState:
    """
    Validate and enrich the budget constraint.
    Sets state['budget_validation'] with result.
    """
    constraints = state.get("constraints", {})
    budget = constraints.get("budget", 0) or 0
    currency = constraints.get("currency", "USD") or "USD"
    num_days = constraints.get("num_days", 1) or 1

    # Convert to USD
    try:
        result = asyncio.run(get_exchange_rate(currency, "USD"))
        usd_rate = 1.0 / result["rate"] if result["rate"] else 1.0
        # ExchangeRate-API gives FROM→EGP; we need FROM→USD
        # Re-fetch USD rate directly
        usd_result = asyncio.run(get_exchange_rate(currency, "USD"))
        budget_usd = budget * (usd_result.get("rate") or 1.0)
    except Exception as e:
        logger.warning("Currency conversion failed: %s — assuming USD", e)
        budget_usd = float(budget)

    daily_usd = budget_usd / max(num_days, 1)

    # ── Validation checks ─────────────────────────────────────────────────────
    if budget_usd < MIN_DAILY_USD * num_days:
        validation = BudgetValidation(
            is_valid=False,
            reason=(
                f"Your budget of {budget} {currency} (~${budget_usd:.0f} USD) is too low "
                f"for {num_days} days in Egypt. "
                f"Minimum recommended is ${MIN_DAILY_USD * num_days:.0f} USD "
                f"(${MIN_DAILY_USD:.0f}/day covers basic hostel + food + entry fees)."
            ),
            budget_usd=budget_usd,
            tier="insufficient",
            daily_budget_usd=daily_usd,
        )
    elif budget_usd > MAX_TOTAL_USD:
        validation = BudgetValidation(
            is_valid=False,
            reason=(
                f"Budget of {budget} {currency} (~${budget_usd:.0f} USD) seems unusually high. "
                f"Please confirm your budget is correct."
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

    return {**state, "budget_validation": validation}


def should_proceed_after_validation(state: PlanState) -> str:
    """Conditional edge after budget validation."""
    validation = state.get("budget_validation", {})
    if not validation.get("is_valid", False):
        return "invalid_budget"
    return "fetch_data"