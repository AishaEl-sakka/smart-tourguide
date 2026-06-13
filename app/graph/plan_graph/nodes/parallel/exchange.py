"""ExchangeRate-API — free tier, 1500 req/month, no key needed for open endpoint."""
from __future__ import annotations
import httpx
from app.config import get_settings


async def get_exchange_rate(from_currency: str, to_currency: str = "EGP") -> dict:
    """Fetch live exchange rate between two currencies."""
    s = get_settings()
    from_cur = from_currency.upper().strip()
    to_cur = to_currency.upper().strip()

    if from_cur == to_cur:
        return {"rate": 1.0, "from": from_cur, "to": to_cur, "source": "identity"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{s.exchangerate_url}/{from_cur}")
            resp.raise_for_status()
            data = resp.json()
            rates = data.get("rates", {})
            rate = rates.get(to_cur)
            if rate:
                return {"rate": rate, "from": from_cur, "to": to_cur, "source": "exchangerate-api"}
    except Exception as e:
        pass

    # Hardcoded fallbacks (approximate, update periodically)
    fallback_to_egp = {"USD": 48.5, "EUR": 52.0, "GBP": 61.0, "SAR": 12.9, "AED": 13.2}
    egp_rate = fallback_to_egp.get(from_cur, 1.0)
    return {"rate": egp_rate, "from": from_cur, "to": "EGP", "source": "fallback_hardcoded"}