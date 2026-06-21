"""
Day-by-day planner node — single LLM call that consumes aggregated context
and produces the structured JSON itinerary.
"""
from __future__ import annotations
import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage
from app.config import get_llm
from app.prompts.planner import PLANNER_SYSTEM_PROMPT
from app.graph.plan_graph.state import PlanState

logger = logging.getLogger(__name__)


def _build_planner_prompt(ctx: dict) -> str:
    return f"""
Plan a {ctx['num_days']}-day trip to {ctx['destination']} for a {ctx['budget_tier']} traveller.

=== TRIP CONSTRAINTS ===
Budget: {ctx['budget']} {ctx['currency']} (≈ ${ctx['budget_usd']:.0f} USD, ${ctx['daily_budget_usd']:.0f}/day)
Duration: {ctx['num_days']} days
Activity preference: {ctx['activity_type']}
Location: {ctx['location_display']} (lat={ctx['lat']}, lon={ctx['lon']})

=== EXCHANGE RATE ===
1 {ctx['exchange_from']} = {ctx['exchange_rate']:.2f} {ctx['exchange_to']}

=== WEATHER FORECAST ===
{json.dumps(ctx['weather_forecasts'], indent=2)}

=== AVAILABLE ACTIVITIES (from OpenTripMap) ===
{json.dumps(ctx['available_activities'][:12], indent=2)}

=== AVAILABLE HOTELS ===
{json.dumps(ctx['available_hotels'], indent=2)}

=== ROUTING (average travel times) ===
Intra-city: {ctx['avg_intra_city_minutes']} min | Between sites: {ctx['avg_inter_site_minutes']} min

=== DATA QUALITY ===
{json.dumps(ctx['data_quality'], indent=2)}

Now produce the complete JSON itinerary following the schema exactly.
Budget per day: ${ctx['daily_budget_usd']:.0f} USD. Never exceed total budget.
Mark any estimated values clearly in the data_quality.estimated_fields list.
"""


def planner_node(state: PlanState) -> PlanState:
    """Call LLM once with full context → structured JSON plan."""
    ctx = state.get("aggregated_context", {})
    if not ctx:
        return {**state, "error": "Aggregated context missing — cannot plan."}

    llm = get_llm(temperature=0.3)
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=_build_planner_prompt(ctx)),
    ]

    try:
        print("\nAVAILABLE HOTELS:")
        print(ctx["available_hotels"])

        print("\nAVAILABLE ACTIVITIES:")
        print(ctx["available_activities"][:5])
        response = llm.invoke(messages)
        raw = response.content.strip()

        # Strip markdown fences
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        plan = json.loads(raw)
        logger.info(
            "Plan generated | days=%d | confidence=%s",
            len(plan.get("days", [])),
            plan.get("data_quality", {}).get("confidence", "?"),
        )
        return {**state, "plan_json": plan, "error": None}

    except json.JSONDecodeError as e:
        logger.error("Planner returned invalid JSON: %s", e)
        return {**state, "error": f"Planner returned invalid JSON: {e}"}
    except Exception as e:
        logger.error("Planner LLM call failed: %s", e)
        return {**state, "error": str(e)}