from __future__ import annotations

import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</p\s*>", "\n", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"[ \t\r\f\v]+", " ", html)
    html = re.sub(r"\n\s*\n+", "\n", html)
    return html.strip()


def _guess_name_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        base = host.split(".")[0]
        if base:
            return base[:1].upper() + base[1:]
    except Exception:
        pass
    return ""


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


def _extract_emails(text: str, limit: int = 5) -> List[str]:
    found: List[str] = []
    seen = set()
    for m in _EMAIL_RE.finditer(text):
        e = m.group(0).strip()
        k = e.lower()
        if k in seen:
            continue
        seen.add(k)
        found.append(e)
        if len(found) >= limit:
            break
    return found


def _looks_like_title_not_location(line: str) -> bool:
    low = line.lower().strip()
    # Common SEO/title separators
    if " - wikipedia" in low or "| wikipedia" in low:
        return True
    if low.endswith("| tesla") or low.endswith("- tesla") or low.endswith("– tesla"):
        return True
    if " - youtube" in low or "| youtube" in low:
        return True
    # If it contains "wikipedia" at all, almost certainly not HQ text
    if "wikipedia" in low:
        return True
    return False


def _extract_location_line(text: str) -> Optional[str]:
    """
    Strict heuristic for HQ/location/address lines.
    Returns None unless we see a line that looks like a real location.
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return None

    # Reject timeline-like lines (years)
    yearish = re.compile(r"\b(19|20)\d{2}\b")
    year_range = re.compile(r"\b(19|20)\d{2}\s*[–-]\s*(19|20)\d{2}\b")

    street_tokens = [
        "street",
        "st.",
        "st ",
        "road",
        "rd.",
        "rd ",
        "ave",
        "avenue",
        "blvd",
        "boulevard",
        "lane",
        "ln",
        "drive",
        "dr",
        "suite",
        "ste",
        "floor",
        "fl",
        "building",
        "bldg",
        "straße",
        "strasse",
        "platz",
        "weg",
        "postal",
        "postcode",
        "zip",
    ]

    city_comma = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{1,40},\s*[A-Za-zÀ-ÿ .'-]{2,40}$")

    for ln in lines:
        if _looks_like_title_not_location(ln):
            continue

        # Reject anything that looks like a year range / timeline
        if year_range.search(ln) or ("(" in ln and yearish.search(ln)):
            continue

        low = ln.lower()

        # address-like: number + address token
        if re.search(r"\b\d{1,5}\b", ln) and any(t in low for t in street_tokens):
            if 10 <= len(ln) <= 180:
                return ln

        # "City, Region/Country" pattern
        if city_comma.match(ln) and len(ln) <= 80:
            return ln

    return None


def _extract_about_snippet(text: str, max_len: int = 450) -> str:
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    for p in parts[:40]:
        # skip title-ish lines
        if _looks_like_title_not_location(p):
            continue
        if len(p) >= 90:
            return (p[: max_len - 1] + "…") if len(p) > max_len else p
    return (text[: max_len - 1] + "…") if len(text) > max_len else text


_SOCIAL_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "twitter.com",
    "x.com",
    "www.x.com",
    "www.twitter.com",
    "tiktok.com",
    "www.tiktok.com",
}


def _extract_social_links(html: str, base_url: str, limit: int = 20) -> List[str]:
    # naive href extractor
    hrefs = re.findall(r'''href\s*=\s*["']([^"']+)["']''', html, flags=re.I)
    out: List[str] = []
    seen = set()

    for h in hrefs:
        h = h.strip()
        if not h or h.startswith("#") or h.lower().startswith("mailto:"):
            continue
        abs_url = urljoin(base_url, h)
        try:
            host = urlparse(abs_url).netloc.lower()
        except Exception:
            continue
        if host in _SOCIAL_HOSTS:
            key = abs_url.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(abs_url)
            if len(out) >= limit:
                break

    return out


def extract_company_facts_fallback(
    company: str,
    objective: str,
    selected_urls: List[str],
    settings,
    max_pages: int = 2,
) -> Dict:
    urls = selected_urls[:max_pages]

    pages: List[Dict] = []
    all_text_chunks: List[str] = []
    social_links: List[str] = []

    with httpx.Client(timeout=settings.timeout_seconds, follow_redirects=True) as client:
        for url in urls:
            try:
                r = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                html = r.text
                text = _html_to_text(html)
                all_text_chunks.append(text)
                social_links.extend(_extract_social_links(html, base_url=url))
                pages.append({"url": url, "ok": True})
            except Exception as e:
                pages.append({"url": url, "ok": False, "error": str(e)})

    all_text = "\n".join([t for t in all_text_chunks if t])

    name_value = company.strip() or (_guess_name_from_url(urls[0]) if urls else "")
    about_value = _extract_about_snippet(all_text) if all_text else ""
    location_value = _extract_location_line(all_text) or ""
    emails = _extract_emails(all_text, limit=5)

    # Dedupe social links
    dedup_social = []
    seen = set()
    for s in social_links:
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        dedup_social.append(s)

    report = {
        "company_identifiers": {
            "name": {"value": name_value, "evidence": urls[:1]},
            "headquarters": {"value": location_value, "evidence": urls[:1] if location_value else []},
        },
        "business_snapshot": {
            "business_units": [],
            "products_services": [],
            "target_industries": [],
        },
        "leadership_signals": {"executives": []},
        "strategic_initiatives": [],
        "evidence": sorted({u for u in selected_urls if isinstance(u, str) and u.strip()}),
        "fallback_notes": {
            "mode": "no_firecrawl",
            "objective": objective,
            "pages_fetched": pages,
            "about_snippet": about_value,
            "emails_found": emails,
            "social_links_found": dedup_social,
        },
    }

    # Put "contacts" into strategic_initiatives so they surface in your current reporting UI
    for e in emails:
        report["strategic_initiatives"].append({"value": f"Contact email: {e}", "evidence": urls[:1]})

    for s in dedup_social:
        report["strategic_initiatives"].append({"value": f"Official social link: {s}", "evidence": urls[:1]})

    # If user asked for "about", place it as a strategic initiative entry too (so it shows up)
    if about_value:
        report["strategic_initiatives"].insert(0, {"value": f"About: {about_value}", "evidence": urls[:1]})

    return report