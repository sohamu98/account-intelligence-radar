"""Utility functions: URL filtering, JSON parsing, Markdown generation."""
import json
import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Domains to exclude (LinkedIn blocked per ToS + rate limits; social media not useful for intel)
BLOCKED_DOMAINS = {
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "tiktok.com",
    "pinterest.com",
    "snapchat.com",
}


def filter_urls(urls: list[str], blocked_domains: Optional[set[str]] = None) -> list[str]:
    """Filter out URLs from blocked domains (e.g., LinkedIn per ToS).
    
    Args:
        urls: List of URLs to filter
        blocked_domains: Set of domains to block. Defaults to BLOCKED_DOMAINS.
    
    Returns:
        Filtered list of URLs
    """
    if blocked_domains is None:
        blocked_domains = BLOCKED_DOMAINS
    
    filtered = []
    for url in urls:
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            # Check if the hostname or any parent domain is blocked
            domain_parts = hostname.lower().split(".")
            is_blocked = False
            for i in range(len(domain_parts) - 1):
                candidate = ".".join(domain_parts[i:])
                if candidate in blocked_domains:
                    is_blocked = True
                    logger.debug("Filtered blocked domain URL: %s", url)
                    break
            if not is_blocked:
                filtered.append(url)
        except Exception:
            logger.debug("Skipping malformed URL: %s", url)
    
    return filtered


def safe_parse_json(text: str) -> Optional[dict[str, Any]]:
    """Safely parse JSON from LLM response, handling markdown code blocks.
    
    Args:
        text: Raw text potentially containing JSON, possibly wrapped in markdown.
    
    Returns:
        Parsed dict or None if parsing fails.
    """
    if not text or not text.strip():
        return None
    
    # Try direct parse first
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # Try to extract from markdown code block ```json ... ```
    pattern = r"```(?:json)?\s*([\s\S]*?)```"
    match = re.search(pattern, text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object within the text
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    
    logger.warning("Failed to parse JSON from LLM response")
    return None


def report_to_markdown(report_data: dict[str, Any]) -> str:
    """Convert an intelligence report dict to a clean Markdown string.
    
    Args:
        report_data: Dictionary representation of an IntelligenceReport.
    
    Returns:
        Markdown-formatted string.
    """
    lines = []
    
    # Header
    identifiers = report_data.get("company_identifiers", {})
    company_name = identifiers.get("name", "Unknown Company")
    lines.append(f"# Intelligence Report: {company_name}")
    lines.append(f"*Generated: {report_data.get('generated_at', 'N/A')}*")
    lines.append("")
    
    # Company Identifiers
    lines.append("## Company Identifiers")
    if identifiers.get("headquarters"):
        lines.append(f"- **Headquarters**: {identifiers['headquarters']}")
    if identifiers.get("website"):
        lines.append(f"- **Website**: {identifiers['website']}")
    if identifiers.get("founded"):
        lines.append(f"- **Founded**: {identifiers['founded']}")
    if identifiers.get("industry"):
        lines.append(f"- **Industry**: {identifiers['industry']}")
    lines.append("")
    
    # Business Snapshot
    snapshot = report_data.get("business_snapshot", {})
    lines.append("## Business Snapshot")
    
    if snapshot.get("business_units"):
        lines.append("### Business Units")
        for unit in snapshot["business_units"]:
            lines.append(f"- {unit}")
        lines.append("")
    
    if snapshot.get("products_and_services"):
        lines.append("### Products & Services")
        for item in snapshot["products_and_services"]:
            lines.append(f"- {item}")
        lines.append("")
    
    if snapshot.get("target_industries"):
        lines.append("### Target Industries")
        for ind in snapshot["target_industries"]:
            lines.append(f"- {ind}")
        lines.append("")
    
    if snapshot.get("revenue"):
        lines.append(f"**Revenue**: {snapshot['revenue']}")
    if snapshot.get("employees"):
        lines.append(f"**Employees**: {snapshot['employees']}")
    lines.append("")
    
    # Leadership Signals
    leadership = report_data.get("leadership_signals", {})
    lines.append("## Leadership Signals")
    lines.append(f"*{leadership.get('note', 'From official public sources only')}*")
    lines.append("")
    executives = leadership.get("executives", [])
    if executives:
        for exec_info in executives:
            name = exec_info.get("name", "N/A")
            title = exec_info.get("title", "N/A")
            lines.append(f"- **{name}** — {title}")
    else:
        lines.append("*No executive data found in official sources.*")
    lines.append("")
    
    # Strategic Initiatives
    initiatives = report_data.get("strategic_initiatives", {})
    lines.append("## Strategic Initiatives")
    
    initiative_sections = [
        ("transformation", "Transformation"),
        ("erp_implementations", "ERP Implementations"),
        ("ai_initiatives", "AI Initiatives"),
        ("supply_chain", "Supply Chain"),
        ("investments", "Investments"),
        ("expansions", "Expansions"),
        ("other", "Other Initiatives"),
    ]
    
    for key, title in initiative_sections:
        items = initiatives.get(key, [])
        if items:
            lines.append(f"### {title}")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")
    
    # Evidence Sources
    sources = report_data.get("evidence_sources", [])
    if sources:
        lines.append("## Evidence Sources")
        for i, source in enumerate(sources, 1):
            url = source.get("url", "N/A")
            title = source.get("title", "")
            relevance = source.get("relevance", "")
            if title:
                lines.append(f"{i}. [{title}]({url})")
            else:
                lines.append(f"{i}. <{url}>")
            if relevance:
                lines.append(f"   *{relevance}*")
        lines.append("")
    
    # Data quality note
    if report_data.get("data_quality_note"):
        lines.append(f"> **Note**: {report_data['data_quality_note']}")
    
    return "\n".join(lines)


def geography_result_to_markdown(result_data: dict[str, Any]) -> str:
    """Convert a geography result dict to Markdown.
    
    Args:
        result_data: Dictionary representation of a GeographyResult.
    
    Returns:
        Markdown-formatted string.
    """
    lines = []
    lines.append(f"# Geography Intelligence Report: {result_data.get('location', 'N/A')}")
    lines.append(f"**Criteria**: {result_data.get('criteria', 'N/A')}")
    lines.append(f"*Generated: {result_data.get('generated_at', 'N/A')}*")
    lines.append("")
    
    companies = result_data.get("companies_found", [])
    if companies:
        lines.append("## Companies Discovered")
        for company in companies:
            lines.append(f"- {company}")
        lines.append("")
    
    reports = result_data.get("reports", [])
    if reports:
        lines.append("---")
        lines.append("")
        for report in reports:
            lines.append(report_to_markdown(report))
            lines.append("")
            lines.append("---")
            lines.append("")
    
    return "\n".join(lines)


def report_to_csv_rows(report_data: dict[str, Any]) -> list[list[str]]:
    """Convert intelligence report to CSV rows.
    
    Returns:
        List of [field, value] pairs for CSV export.
    """
    rows = [["Field", "Value"]]
    
    identifiers = report_data.get("company_identifiers", {})
    rows.append(["Company Name", identifiers.get("name", "")])
    rows.append(["Headquarters", identifiers.get("headquarters", "")])
    rows.append(["Website", identifiers.get("website", "")])
    rows.append(["Industry", identifiers.get("industry", "")])
    
    snapshot = report_data.get("business_snapshot", {})
    rows.append(["Business Units", "; ".join(snapshot.get("business_units", []))])
    rows.append(["Products & Services", "; ".join(snapshot.get("products_and_services", []))])
    rows.append(["Target Industries", "; ".join(snapshot.get("target_industries", []))])
    rows.append(["Revenue", snapshot.get("revenue", "")])
    rows.append(["Employees", snapshot.get("employees", "")])
    
    leadership = report_data.get("leadership_signals", {})
    execs = leadership.get("executives", [])
    exec_str = "; ".join(f"{e.get('name', '')} ({e.get('title', '')})" for e in execs)
    rows.append(["Executives", exec_str])
    
    initiatives = report_data.get("strategic_initiatives", {})
    rows.append(["Transformation", "; ".join(initiatives.get("transformation", []))])
    rows.append(["AI Initiatives", "; ".join(initiatives.get("ai_initiatives", []))])
    rows.append(["ERP Implementations", "; ".join(initiatives.get("erp_implementations", []))])
    rows.append(["Investments", "; ".join(initiatives.get("investments", []))])
    rows.append(["Expansions", "; ".join(initiatives.get("expansions", []))])
    
    sources = report_data.get("evidence_sources", [])
    urls = "; ".join(s.get("url", "") for s in sources)
    rows.append(["Evidence Sources", urls])
    rows.append(["Generated At", report_data.get("generated_at", "")])
    
    return rows
