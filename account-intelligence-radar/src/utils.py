from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse


BLOCKED_DOMAINS = {
    "linkedin.com",
    "www.linkedin.com",
    "facebook.com",
    "www.facebook.com",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
}


def ensure_dirs(settings) -> None:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.cache_dir / "serp").mkdir(parents=True, exist_ok=True)
    (settings.cache_dir / "llm_select").mkdir(parents=True, exist_ok=True)
    (settings.cache_dir / "firecrawl").mkdir(parents=True, exist_ok=True)


def sanitize_company_slug(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "company"


def canonicalize_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        # drop fragments; keep query (sometimes investor relations pages use it)
        cleaned = p._replace(fragment="")
        return urlunparse(cleaned)
    except Exception:
        return url.strip()


def is_blocked_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return host in BLOCKED_DOMAINS or any(host.endswith("." + d) for d in BLOCKED_DOMAINS)
    except Exception:
        return False


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")