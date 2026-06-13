"""
Data aggregator node — merges all parallel results into a clean context
dict for the planner LLM. Handles missing/failed sources gracefully.
"""
from __future__ import annotations
from app.graph.plan_graph.state import PlanState


def aggregator_node(state: PlanState) -> PlanState:
    """
    Merge parallel API results + constraints + validation into one
    clean context dict stored in state for the planner node.
    """
    constraints   = state.get("constraints", {})
    validation    = state.get("budget_validation", {})
    parallel_data = state.get("parallel_data", {})

    geocode    = parallel_data.get("geocode", {})
    weather    = parallel_data.get("weather", {})
    activities = parallel_data.get("activities", {})
    hotels     = parallel_data.get("hotels", {})
    routing    = parallel_data.get("routing", {})
    exchange   = parallel_data.get("exchange", {})

    # Track data quality
    sources_used: list[str] = []
    estimated_fields: list[str] = []

    for name, data in [("geocode", geocode), ("weather", weather),
                        ("activities", activities), ("hotels", hotels),
                        ("routing", routing), ("exchange", exchange)]:
        src = data.get("source", "unknown")
        sources_used.append(f"{name}:{src}")
        if "error" in data or src in ("fallback", "fallback_hardcoded", "osrm_estimate"):
            estimated_fields.append(name)

    confidence = (
        "high"   if len(estimated_fields) == 0 else
        "medium" if len(estimated_fields) <= 2 else
        "low"
    )

    aggregated_context = {
        # User intent
        "destination":   constraints.get("destination", "Egypt"),
        "num_days":      constraints.get("num_days", 5),
        "budget":        constraints.get("budget"),
        "currency":      constraints.get("currency", "USD"),
        "activity_type": constraints.get("activity_type", "mixed"),

        # Validated budget
        "budget_usd":       validation.get("budget_usd", 0),
        "daily_budget_usd": validation.get("daily_budget_usd", 0),
        "budget_tier":      validation.get("tier", "mid-range"),

        # Location
        "lat": geocode.get("lat"),
        "lon": geocode.get("lon"),
        "location_display": geocode.get("display_name", constraints.get("destination")),

        # Weather
        "weather_forecasts": weather.get("forecasts", []),

        # Activities
        "available_activities": activities.get("activities", []),

        # Hotels
        "available_hotels":      hotels.get("hotels", []),
        "budget_per_night_usd":  hotels.get("budget_per_night_usd", 0),

        # Routing
        "avg_intra_city_minutes": routing.get("avg_intra_city_minutes", 25),
        "avg_inter_site_minutes": routing.get("avg_inter_site_minutes", 45),

        # Exchange
        "exchange_rate":    exchange.get("rate", 1.0),
        "exchange_from":    exchange.get("from", "USD"),
        "exchange_to":      exchange.get("to", "EGP"),

        # Data quality metadata
        "data_quality": {
            "sources_used":      sources_used,
            "estimated_fields":  estimated_fields,
            "confidence":        confidence,
        },
    }

    return {**state, "aggregated_context": aggregated_context}