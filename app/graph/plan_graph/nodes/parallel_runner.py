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
    daily_usd = validation.get("daily_budget_usd", 100.0)
    currency = constraints.get("currency", "USD")

    geo = await geocode_destination(destination)

    lat = geo["lat"]
    lon = geo["lon"]

    budget_per_night = daily_usd * 0.35

    weather_task = fetch_weather(lat, lon, num_days)
    activities_task = fetch_activities(lat, lon, activity_type)
    hotels_task = fetch_hotels(lat, lon, budget_per_night)
    routing_task = estimate_city_routing(lat, lon)
    exchange_task = get_exchange_rate(currency, "EGP")

    weather, activities, hotels, routing, exchange = await asyncio.gather(
        weather_task,
        activities_task,
        hotels_task,
        routing_task,
        exchange_task,
    )

    return ParallelData(
        geocode=geo,
        weather=weather,
        activities=activities,
        hotels=hotels,
        routing=routing,
        exchange=exchange,
    )


async def parallel_runner_node(state: PlanState) -> PlanState:
    try:
        parallel_data = await _run_all_parallel(state)

        logger.info(
            "Parallel fetch complete | activities=%d | hotels=%d",
            len(parallel_data["activities"].get("activities", [])),
            len(parallel_data["hotels"].get("hotels", [])),
        )

        return {
            **state,
            "parallel_data": parallel_data,
        }

    except Exception as e:
        logger.exception("Parallel data fetch failed")

        return {
            **state,
            "error": str(e),
        }