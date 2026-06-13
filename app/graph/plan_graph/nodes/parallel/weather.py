"""Open-Meteo weather — free, unlimited, no key."""
from __future__ import annotations
import httpx
from app.config import get_settings


async def fetch_weather(lat: float, lon: float, num_days: int) -> dict:
    """Fetch daily weather forecast for the destination."""
    s = get_settings()
    days = min(num_days, 7)  # API limit is 16 days but we cap at 7
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                s.openmeteo_url,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
                    "forecast_days": days,
                    "timezone": "Africa/Cairo",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            daily = data.get("daily", {})
            forecasts = []
            dates = daily.get("time", [])
            for i, date in enumerate(dates):
                forecasts.append({
                    "date": date,
                    "max_temp_c": daily.get("temperature_2m_max", [None])[i],
                    "min_temp_c": daily.get("temperature_2m_min", [None])[i],
                    "precipitation_mm": daily.get("precipitation_sum", [0])[i] or 0,
                    "weather_code": daily.get("weathercode", [0])[i] or 0,
                    "description": _weather_code_to_text(daily.get("weathercode", [0])[i] or 0),
                })
            return {"forecasts": forecasts, "source": "open-meteo"}
    except Exception as e:
        return {"forecasts": [], "source": "open-meteo", "error": str(e)}


def _weather_code_to_text(code: int) -> str:
    mapping = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 51: "Light drizzle", 61: "Light rain", 71: "Light snow",
        80: "Rain showers", 95: "Thunderstorm",
    }
    for k in sorted(mapping.keys(), reverse=True):
        if code >= k:
            return mapping[k]
    return "Unknown"