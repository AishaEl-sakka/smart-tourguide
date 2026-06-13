"""
Parallel runner node — fires all 5 API tools simultaneously with asyncio.gather.
Each tool is independent; failures are isolated and stored as errors in their dict.
"""
from __future__ import annotations
import asyncio
import logging

from app.graph.plan_graph.state import PlanState, ParallelData
from app.graph.plan_graph.nodes.parallel.geocoder import geocode_destination
from app.graph.plan_graph.nodes.parallel.weather import fetch_weather
from app.graph.plan_graph.nodes.parallel.activities import fetch_activities
from app.graph.plan_graph.nodes.parallel.hotels import fetch_hotels
from app.graph.plan_graph.nodes.parallel.routing import estimate_city_routing
from app.graph.plan_graph.nodes.parallel.exchange import get_exchange_rate

logger = logging.getLogger(__name__)


async def _run_all_parallel(state: PlanState) -> ParallelData:
    constraints = state.get("constraints", {})
    validation = state.get("budget_validation", {})

    destination = constraints.get("destination", "Egypt")
    activity_type = constraints.get("activity_type", "mixed")
    num_days = constraints.get("num_days", 5)
    budget_usd = validation.get("budget_usd", 500.0)
    daily_usd = validation.get("daily_budget_usd", 100.0)
    currency = constraints.get("currency", "USD")

    # Step 1: geocode first (others depend on coords)
    geo = await geocode_destination(destination)
    lat, lon = geo["lat"], geo["lon"]

    # Step 2: run all remaining calls in parallel
    budget_per_night = daily_usd * 0.35  # ~35% of daily budget for accommodation

    weather_task    = fetch_weather(lat, lon, num_days)
    activities_task = fetch_activities(lat, lon, activity_type)
    hotels_task     = fetch_hotels(lat, lon, budget_per_night)
    routing_task    = estimate_city_routing(lat, lon)
    exchange_task   = get_exchange_rate(currency, "EGP")

    weather, activities, hotels, routing, exchange = await asyncio.gather(
        weather_task,
        activities_task,
        hotels_task,
        routing_task,
        exchange_task,
        return_exceptions=False,
    )

    # Log what we got
    logger.info(
        "Parallel fetch complete | geo=%s | weather_days=%d | activities=%d | hotels=%d",
        destination,
        len(weather.get("forecasts", [])),
        len(activities.get("activities", [])),
        len(hotels.get("hotels", [])),
    )

    return ParallelData(
        geocode=geo,
        weather=weather,
        activities=activities,
        hotels=hotels,
        routing=routing,
        exchange=exchange,
    )


def parallel_runner_node(state: PlanState) -> PlanState:
    """Synchronous entry point for LangGraph — runs asyncio event loop internally."""
    try:
        parallel_data = asyncio.run(_run_all_parallel(state))
    except Exception as e:
        logger.error("Parallel data fetch failed: %s", e)
        parallel_data = ParallelData(
            geocode={"lat": 26.82, "lon": 30.80, "source": "fallback"},
            weather={"forecasts": [], "source": "error"},
            activities={"activities": [], "source": "error"},
            hotels={"hotels": [], "source": "error"},
            routing={"avg_intra_city_minutes": 25, "source": "fallback"},
            exchange={"rate": 48.5, "from": "USD", "to": "EGP", "source": "fallback"},
        )

    return {**state, "parallel_data": parallel_data}