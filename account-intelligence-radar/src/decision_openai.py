from __future__ import annotations

import json
from typing import Dict, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils import sha256_text, load_json, save_json, canonicalize_url, is_blocked_url


SYSTEM = (
    "You are a careful research analyst selecting web sources for business outreach intelligence. "
    "Return ONLY valid JSON. No markdown."
)

def _build_user_prompt(company: str, objective: str, serp_results: List[Dict[str, str]], k: int) -> str:
    items = []
    for i, r in enumerate(serp_results, start=1):
        items.append(
            {
                "rank": i,
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("snippet", ""),
            }
        )

    return (
        f"Company: {company}\n"
        f"Objective: {objective}\n\n"
        f"From the search results below, select exactly {k} URLs that are most likely to contain "
        f"credible, official, and relevant information to satisfy the objective.\n"
        f"Constraints:\n"
        f"- Return exactly {k} items.\n"
        f"- Exclude LinkedIn and social media.\n"
        f"- Prefer official company domain, investor relations, annual reports, press releases, "
        f"and reputable sources (e.g., encyclopedia/registries) if needed.\n\n"
        f"Return JSON ONLY in this format:\n"
        f'{{"selected":[{{"url":"...","reason":"..."}}]}}\n\n'
        f"Search results:\n{json.dumps(items, ensure_ascii=False)}"
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=6))
def _openai_chat(settings, system: str, user: str) -> Dict:
    # Minimal raw REST call (no extra SDK dependency)
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4.1-mini",
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    with httpx.Client(timeout=settings.timeout_seconds) as client:
        r = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        # Handle typical auth/quota errors upstream by raising
        r.raise_for_status()
        return r.json()


def select_top_urls_openai(company: str, objective: str, serp_results: List[Dict[str, str]], settings, k: int = 5):
    cache_key = sha256_text("llm_select|" + json.dumps({"company": company, "objective": objective, "serp": serp_results, "k": k}, sort_keys=True))
    cache_path = settings.cache_dir / "llm_select" / f"{cache_key}.json"

    if cache_path.exists():
        cached = load_json(cache_path)
        return cached["selected"]

    user_prompt = _build_user_prompt(company, objective, serp_results, k)
    data = _openai_chat(settings=settings, system=SYSTEM, user=user_prompt)

    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)

    selected = parsed.get("selected", [])
    if not isinstance(selected, list) or len(selected) != k:
        raise ValueError(f"Model did not return exactly {k} selected URLs.")

    cleaned = []
    for item in selected:
        url = canonicalize_url(str(item.get("url", "")).strip())
        reason = str(item.get("reason", "")).strip()
        if not url or is_blocked_url(url):
            continue
        cleaned.append({"url": url, "reason": reason})

    # Ensure exactly k after cleaning by filling from serp results
    if len(cleaned) < k:
        existing = {x["url"] for x in cleaned}
        for r in serp_results:
            u = canonicalize_url(r["url"])
            if u in existing or is_blocked_url(u):
                continue
            cleaned.append({"url": u, "reason": "Fallback from SERP results (LLM output incomplete after filtering)."})
            existing.add(u)
            if len(cleaned) == k:
                break

    if len(cleaned) != k:
        raise ValueError("Unable to produce exactly 5 URLs after cleanup/fallback.")

    save_json(cache_path, {"selected": cleaned})
    return cleaned


def select_top_urls_heuristic(serp_results: List[Dict[str, str]], k: int = 5):
    """
    Deterministic fallback if OpenAI fails: prioritize shorter, cleaner URLs and likely official domains.
    """
    def score(r: Dict[str, str]) -> float:
        url = r.get("url", "")
        s = 0.0
        if any(token in url.lower() for token in ["investor", "annual", "report", "about", "company", "who-we-are", "press", "news"]):
            s += 2.0
        if len(url) < 80:
            s += 0.5
        if r.get("snippet"):
            s += 0.2
        return s

    filtered = [r for r in serp_results if r.get("url") and not is_blocked_url(r["url"])]
    ranked = sorted(filtered, key=score, reverse=True)
    out = []
    for r in ranked[:k]:
        out.append({"url": canonicalize_url(r["url"]), "reason": "Heuristic selection (OpenAI unavailable)."})
    return out