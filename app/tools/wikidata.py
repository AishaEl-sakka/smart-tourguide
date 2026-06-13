"""
WikiData SPARQL tool — free, unlimited. Used by Q&A agent for structured
facts about Egyptian sites, historical figures, and geography.
"""
from __future__ import annotations
import httpx
from langchain_core.tools import tool
from app.config import get_settings


COMMON_QUERIES = {
    "site_info": """
        SELECT ?item ?itemLabel ?description ?coord ?image ?inception WHERE {{
          ?item wdt:P31/wdt:P279* wd:Q839954 ;
                wdt:P17 wd:Q79 .
          ?item rdfs:label "{name}"@en .
          OPTIONAL {{ ?item wdt:P625 ?coord }}
          OPTIONAL {{ ?item wdt:P18 ?image }}
          OPTIONAL {{ ?item wdt:P571 ?inception }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
        }} LIMIT 1
    """,
}


@tool
def wikidata_search(query: str) -> str:
    """
    Query WikiData SPARQL endpoint for structured facts about Egyptian
    historical sites, pharaohs, cities, or landmarks.

    Args:
        query: Natural language query about an Egyptian site or figure
               (e.g. 'Karnak Temple', 'Ramesses II', 'Valley of the Kings')

    Returns:
        Structured facts as a formatted string.
    """
    s = get_settings()

    # Build a text-search SPARQL query
    sparql = f"""
    SELECT DISTINCT ?item ?itemLabel ?itemDescription ?coord WHERE {{
      ?item wdt:P17 wd:Q79 ;
            rdfs:label ?label .
      FILTER(CONTAINS(LCASE(?label), LCASE("{query}")))
      FILTER(LANG(?label) = "en")
      OPTIONAL {{ ?item wdt:P625 ?coord }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
    }} LIMIT 5
    """

    try:
        resp = httpx.get(
            s.wikidata_sparql_url,
            params={"query": sparql, "format": "json"},
            headers={"Accept": "application/sparql-results+json",
                     "User-Agent": "EgyptTourismBot/1.0"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        bindings = data.get("results", {}).get("bindings", [])

        if not bindings:
            return f"No WikiData results found for: {query}"

        lines = [f"WikiData facts for '{query}':"]
        for b in bindings:
            label = b.get("itemLabel", {}).get("value", "Unknown")
            desc = b.get("itemDescription", {}).get("value", "No description")
            coord = b.get("coord", {}).get("value", "")
            lines.append(f"\n• {label}: {desc}")
            if coord:
                lines.append(f"  Location: {coord}")

        return "\n".join(lines)

    except Exception as e:
        return f"WikiData query failed: {e}"