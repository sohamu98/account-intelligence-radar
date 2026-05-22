from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils import canonicalize_url, is_blocked_url, sha256_text, load_json, save_json


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _serpapi_request(params: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    with httpx.Client(timeout=timeout) as client:
        r = client.get("https://serpapi.com/search.json", params=params)
        r.raise_for_status()
        return r.json()


def discover_urls_serpapi(query: str, settings, limit: int = 20) -> List[Dict[str, str]]:
    """
    Returns normalized SERP results: [{title, url, snippet, source}]
    """
    cache_key = sha256_text(f"serp|{query}|{limit}")
    cache_path = settings.cache_dir / "serp" / f"{cache_key}.json"

    if cache_path.exists():
        data = load_json(cache_path)
    else:
        params = {
            "engine": "google",
            "q": query,
            "api_key": settings.serpapi_api_key,
            "num": min(10, limit),  # google typically supports 10 per page; keep simple
        }
        data = _serpapi_request(params=params, timeout=settings.timeout_seconds)
        save_json(cache_path, data)

    organic = data.get("organic_results", []) or []
    results: List[Dict[str, str]] = []
    for item in organic:
        link = (item.get("link") or "").strip()
        if not link:
            continue
        link = canonicalize_url(link)
        if is_blocked_url(link):
            continue
        results.append(
            {
                "title": (item.get("title") or "").strip(),
                "url": link,
                "snippet": (item.get("snippet") or "").strip(),
                "source": "serpapi",
            }
        )
        if len(results) >= limit:
            break

    # de-dup by URL
    seen = set()
    deduped = []
    for r in results:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        deduped.append(r)
    return deduped