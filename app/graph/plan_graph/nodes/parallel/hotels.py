"""OpenTripMap hotels — shared quota with activities (1000 req/day)."""
from __future__ import annotations
import httpx
from app.config import get_settings


async def fetch_hotels(lat: float, lon: float, budget_per_night_usd: float) -> dict:
    """Fetch hotel options near the destination centroid."""
    print("FETCH_HOTELS CALLED")
    s = get_settings()
    if not s.opentripmap_api_key:
        return {"hotels": [], "source": "opentripmap", "error": "no API key"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{s.opentripmap_url}/places/radius",
                params={
                    "radius": 5000,
                    "lon": lon,
                    "lat": lat,
                    #"kinds": "accommodations",
                    "format": "json",
                    "limit": 10,
                    "apikey": s.opentripmap_api_key,
                },
            )
            resp.raise_for_status()

            print("\nHOTEL STATUS:", resp.status_code)
            print("HOTEL URL:", resp.url)

            raw = resp.json()

            print("\nHOTELS RAW RESPONSE:")
            print(raw)
            print("RAW COUNT:", len(raw) if isinstance(raw, list) else "NOT LIST")


            print("\n" + "=" * 50)
            print("HOTELS RAW COUNT:", len( raw))
            print("HOTELS SAMPLE:", raw[:3])
            print("=" * 50 + "\n")

            hotels = [
                {
                    "name": p.get("name", "Unnamed"),
                    "xid": p.get("xid", ""),
                    "lat": p.get("point", {}).get("lat"),
                    "lon": p.get("point", {}).get("lon"),
                    "rate": p.get("rate", 0),
                }
                for p in raw
                if p.get("name")
            ]
            print("PARSED HOTELS:")
            print(hotels)

            return {
                "hotels": hotels[:5],
                "source": "opentripmap",
                "budget_per_night_usd": budget_per_night_usd,
            }

    except Exception as e:
        print("\nHOTELS ERROR:")
        print(type(e))
        print(str(e))

        return {
            "hotels": [],
            "source": "opentripmap",
            "error": str(e)
        }