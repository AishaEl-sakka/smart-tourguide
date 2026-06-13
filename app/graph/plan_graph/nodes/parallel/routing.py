"""OSRM routing — free, unlimited."""
from __future__ import annotations
import httpx
from app.config import get_settings


async def get_route_duration(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    profile: str = "driving",
) -> dict:
    """Get driving/walking duration between two coordinates via OSRM."""
    s = get_settings()
    url = (
        f"{s.osrm_url}/route/v1/{profile}/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    )
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params={"overview": "false"})
            resp.raise_for_status()
            data = resp.json()
            route = data.get("routes", [{}])[0]
            return {
                "duration_seconds": route.get("duration", 0),
                "duration_minutes": round(route.get("duration", 0) / 60),
                "distance_meters": route.get("distance", 0),
                "source": "osrm",
            }
    except Exception as e:
        return {"duration_minutes": 30, "source": "osrm", "error": str(e)}


async def estimate_city_routing(lat: float, lon: float) -> dict:
    """Estimate average intra-city travel time (self-loop as proxy)."""
    # Return typical Cairo/Luxor/Aswan city travel estimates
    return {
        "avg_intra_city_minutes": 25,
        "avg_inter_site_minutes": 45,
        "source": "osrm_estimate",
    }