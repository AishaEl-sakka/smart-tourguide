"""Nominatim geocoder — free, unlimited (1 req/s rate limit)."""
from __future__ import annotations
import asyncio
import httpx
from app.config import get_settings


async def geocode_destination(destination: str) -> dict:
    """Resolve destination name to coordinates using OSM Nominatim."""
    s = get_settings()
    query = f"{destination}, Egypt"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{s.nominatim_url}/search",
                params={"q": query, "format": "json", "limit": 1, "countrycodes": "eg"},
                headers={"User-Agent": "EgyptTourismAgent/1.0 (tourism-planner)"},
            )
            resp.raise_for_status()
            data = resp.json()
            if data:
                return {
                    "lat": float(data[0]["lat"]),
                    "lon": float(data[0]["lon"]),
                    "display_name": data[0].get("display_name", destination),
                    "source": "nominatim",
                }
    except Exception as e:
        pass

    # Egypt center as safe fallback
    return {"lat": 26.8206, "lon": 30.8025, "display_name": "Egypt", "source": "fallback"}