"""OpenTripMap activities — 1000 req/day free."""
from __future__ import annotations
import httpx
from app.config import get_settings

ACTIVITY_KIND_MAP = {
    "cultural":  "historic,museums,architecture,religion",
    "adventure": "natural,sport,amusements",
    "relaxed":   "beaches,spa,interesting_places",
    "mixed":     "historic,natural,museums,beaches,sport",
}


async def fetch_activities(lat: float, lon: float, activity_type: str, radius_m: int = 15000) -> dict:
    """Fetch POIs from OpenTripMap based on activity preference."""
    s = get_settings()
    if not s.opentripmap_api_key:
        return {"activities": [], "source": "opentripmap", "error": "no API key"}

    kinds = ACTIVITY_KIND_MAP.get(activity_type, ACTIVITY_KIND_MAP["mixed"])
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{s.opentripmap_url}/places/radius",
                params={
                    "radius": radius_m,
                    "lon": lon,
                    "lat": lat,
                    "kinds": kinds,
                    "rate": 3,          # min star rating
                    "format": "json",
                    "limit": 20,
                    "apikey": s.opentripmap_api_key,
                },
            )
            resp.raise_for_status()
            raw = resp.json()
            activities = [
                {
                    "name": p.get("name", "Unnamed"),
                    "kinds": p.get("kinds", ""),
                    "xid": p.get("xid", ""),
                    "lat": p.get("point", {}).get("lat"),
                    "lon": p.get("point", {}).get("lon"),
                    "dist": p.get("dist", 0),
                    "rate": p.get("rate", 0),
                }
                for p in raw
                if p.get("name")
            ]
            return {"activities": activities[:15], "source": "opentripmap"}
    except Exception as e:
        return {"activities": [], "source": "opentripmap", "error": str(e)}