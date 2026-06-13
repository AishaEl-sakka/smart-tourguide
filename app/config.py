"""
Central config — reads from .env, exposes LLM factory with Groq→Gemini fallback.
"""
from __future__ import annotations
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────────────
    groq_api_key: str = "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"
    google_api_key: str = "AIzaSyDCP_CKWfDw_V2i6efI3g8jOSsCieJ5CLc"

    groq_model: str = "llama-3.3-70b-versatile"
    gemini_model: str = "gemini-1.5-flash"
    llm_temperature: float = 0.2

    # ── Search ───────────────────────────────────────────────────────────────
    tavily_api_key: str = "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"

    # ── External APIs ────────────────────────────────────────────────────────
    opentripmap_api_key: str = "5ae2e3f221c38a28845f05b69db504b7ec348c35778c4aea0ca9ebdd"

    # Free APIs — base URLs only, no key needed
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    osrm_url: str = "http://router.project-osrm.org"
    openmeteo_url: str = "https://api.open-meteo.com/v1/forecast"
    exchangerate_url: str = "https://open.er-api.com/v6/latest"
    wikidata_sparql_url: str = "https://query.wikidata.org/sparql"
    opentripmap_url: str = "https://api.opentripmap.com/0.1/en"

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    rate_limit_per_minute: int = 30

    # Budget validation constraints (USD equivalent)
    min_budget_usd: float = 100.0
    max_budget_usd: float = 50000.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm(temperature: float | None = None) -> BaseChatModel:
    """
    Return best available LLM: Groq first (faster, free), Gemini as fallback.
    Raises RuntimeError if neither key is configured.
    """
    s = get_settings()
    temp = temperature if temperature is not None else s.llm_temperature

    if s.groq_api_key:
        return ChatGroq(
            model=s.groq_model,
            temperature=temp,
            api_key=s.groq_api_key,
        )

    if s.google_api_key:
        return ChatGoogleGenerativeAI(
            model=s.gemini_model,
            temperature=temp,
            google_api_key=s.google_api_key,
        )

    raise RuntimeError(
        "No LLM configured. Set GROQ_API_KEY or GOOGLE_API_KEY in your .env file."
    )