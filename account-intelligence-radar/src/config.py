from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import os


@dataclass(frozen=True)
class Settings:
    serpapi_api_key: str
    openai_api_key: str
    firecrawl_api_key: str

    # Runtime behavior
    cache_dir: Path = Path("cache")
    reports_dir: Path = Path("reports")

    # HTTP
    timeout_seconds: float = 30.0


def load_settings() -> Settings:
    load_dotenv()

    serp = os.getenv("SERPAPI_API_KEY", "").strip()
    oai = os.getenv("OPENAI_API_KEY", "").strip()
    fire = os.getenv("FIRECRAWL_API_KEY", "").strip()

    # Happy path expects all keys present. We still allow running to demonstrate failure handling,
    # but we will raise if missing so the user knows what to set.
    missing = [name for name, val in [
        ("SERPAPI_API_KEY", serp),
        ("OPENAI_API_KEY", oai),
        ("FIRECRAWL_API_KEY", fire),
    ] if not val]

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Create a .env file (based on .env.example) and set these keys."
        )

    return Settings(
        serpapi_api_key=serp,
        openai_api_key=oai,
        firecrawl_api_key=fire,
    )