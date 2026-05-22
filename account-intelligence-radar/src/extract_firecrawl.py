from __future__ import annotations

import json
from typing import Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils import sha256_text, load_json, save_json


def _schema() -> Dict:
    # “Evidence per claim” structure to satisfy traceability requirement
    return {
        "type": "object",
        "properties": {
            "company_identifiers": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "headquarters": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
            "business_snapshot": {
                "type": "object",
                "properties": {
                    "business_units": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "value": {"type": "string"},
                                "evidence": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    "products_services": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "value": {"type": "string"},
                                "evidence": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    "target_industries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "value": {"type": "string"},
                                "evidence": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                },
            },
            "leadership_signals": {
                "type": "object",
                "properties": {
                    "executives": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "title": {"type": "string"},
                                "evidence": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    }
                },
            },
            "strategic_initiatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "company_identifiers",
            "business_snapshot",
            "leadership_signals",
            "strategic_initiatives",
            "evidence",
        ],
    }


def _http_error_to_runtime_error(prefix: str, e: httpx.HTTPStatusError) -> RuntimeError:
    status = getattr(e.response, "status_code", "unknown")
    body = ""
    try:
        body = e.response.text
    except Exception:
        body = "<no body>"
    return RuntimeError(f"{prefix} HTTP {status}: {body}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _firecrawl_extract(settings, urls: List[str], prompt: str) -> Dict:
    headers = {
        "Authorization": f"Bearer {settings.firecrawl_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "urls": urls,
        "prompt": prompt,
        "schema": _schema(),
        "ignoreSitemap": True,
    }

    with httpx.Client(timeout=settings.timeout_seconds) as client:
        r = client.post("https://api.firecrawl.dev/v1/extract", headers=headers, json=payload)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Turn HTTPStatusError into a RuntimeError with status code + body
            raise _http_error_to_runtime_error("Firecrawl", e) from e
        return r.json()


def extract_company_facts_firecrawl(company: str, objective: str, selected_urls: List[str], settings) -> Dict:
    cache_key = sha256_text(
        "firecrawl|"
        + json.dumps({"company": company, "objective": objective, "urls": selected_urls}, sort_keys=True)
    )
    cache_path = settings.cache_dir / "firecrawl" / f"{cache_key}.json"

    if cache_path.exists():
        return load_json(cache_path)

    prompt = (
        "You are extracting company intelligence for outreach.\n"
        f"Company: {company}\n"
        f"Objective: {objective}\n\n"
        "Rules:\n"
        "- Only include executives if the source explicitly names them (official sources preferred).\n"
        "- Every claim must include at least one evidence URL.\n"
        "- If a field is not found, return empty string/empty list, not fabricated values.\n"
    )

    raw = _firecrawl_extract(settings=settings, urls=selected_urls, prompt=prompt)

    # Firecrawl responses can vary; normalize to a single object.
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Unexpected Firecrawl response shape: {list(raw.keys()) if isinstance(raw, dict) else type(raw)}"
        )

    # Ensure evidence includes selected URLs at minimum
    evidence = set(selected_urls)
    if isinstance(data.get("evidence"), list):
        for u in data["evidence"]:
            if isinstance(u, str) and u.strip():
                evidence.add(u.strip())
    data["evidence"] = sorted(evidence)

    save_json(cache_path, data)
    return data