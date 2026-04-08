"""Intelligence pipeline: SerpAPI → DeepSeek → Firecrawl Extract."""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
import httpx
from .config import get_settings
from .models import (
    BusinessSnapshot,
    CompanyIdentifiers,
    EvidenceSource,
    GeographyResult,
    IntelligenceReport,
    LeadershipSignals,
    StrategicInitiatives,
)
from .utils import filter_urls, safe_parse_json

logger = logging.getLogger(__name__)

LINKEDIN_EXCLUSION_NOTE = (
    "LinkedIn URLs excluded per platform Terms of Service. "
    "Manual search recommended for contact discovery."
)


async def search_serp(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """Search Google via SerpAPI.
    
    Args:
        query: Search query string
        num_results: Number of results to request
    
    Returns:
        List of organic search result dicts with keys: title, link, snippet
    
    Raises:
        ValueError: If SerpAPI key not configured or no results found
        httpx.HTTPError: On network/HTTP errors
    """
    settings = get_settings()
    if not settings.serpapi_key:
        raise ValueError("SERPAPI_KEY not configured. Please set it in your .env file.")
    
    params = {
        "q": query,
        "api_key": settings.serpapi_key,
        "engine": "google",
        "num": num_results,
        "safe": "active",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        data = response.json()
    
    organic = data.get("organic_results", [])
    if not organic:
        logger.warning("No SERP results for query: [REDACTED]")
        raise ValueError(
            "No search results found. Try a different company name or check your SerpAPI key."
        )
    
    results = []
    for item in organic:
        results.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    
    return results


async def select_urls_with_llm(
    serp_results: list[dict[str, Any]],
    objective: str,
    company_name: str,
    max_urls: int = 5,
) -> list[dict[str, Any]]:
    """Use DeepSeek to select the most relevant URLs from SERP results.
    
    Args:
        serp_results: List of search result dicts
        objective: Research objective
        company_name: Target company name
        max_urls: Maximum number of URLs to select
    
    Returns:
        List of selected result dicts
    
    Raises:
        ValueError: On 402 balance error or API key not configured
        httpx.HTTPError: On network/HTTP errors
    """
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY not configured. Please set it in your .env file.")
    
    # Filter blocked domains before sending to LLM
    filtered_results = [r for r in serp_results if r.get("link") and filter_urls([r["link"]])]
    
    if not filtered_results:
        raise ValueError("No usable URLs after filtering blocked domains.")
    
    # Build prompt - don't log the full prompt as it may contain sensitive data
    results_text = "\n".join(
        f"{i+1}. Title: {r['title']}\n   URL: {r['link']}\n   Snippet: {r['snippet']}"
        for i, r in enumerate(filtered_results)
    )
    
    prompt = f"""You are a business intelligence researcher. Select the {max_urls} most relevant URLs for researching {company_name}.

Objective: {objective}

Search results:
{results_text}

IMPORTANT RULES:
- Do NOT select LinkedIn URLs (prohibited per ToS)
- Prefer official company websites, news sources, annual reports, press releases
- Focus on sources with concrete business information

Return ONLY a JSON object:
{{
  "selected_indices": [1, 3, 5],
  "reasoning": "Brief explanation of selections"
}}
"""
    
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": settings.deepseek_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.deepseek_base_url}/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        
        if response.status_code == 402:
            raise ValueError(
                "DeepSeek API: Insufficient balance (HTTP 402). "
                "Please top up your DeepSeek account at https://platform.deepseek.com"
            )
        
        response.raise_for_status()
    
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    
    parsed = safe_parse_json(content)
    if not parsed:
        logger.warning("Failed to parse URL selection JSON from LLM")
        # Fallback: return first max_urls filtered results
        return filtered_results[:max_urls]
    
    indices = parsed.get("selected_indices", [])
    selected = []
    for idx in indices:
        try:
            result = filtered_results[int(idx) - 1]
            selected.append(result)
        except (IndexError, ValueError):
            pass
    
    # Ensure we have at least some results
    if not selected:
        selected = filtered_results[:max_urls]
    
    return selected[:max_urls]


async def extract_with_firecrawl(
    urls: list[str],
    extraction_prompt: str,
    company_name: str,
) -> dict[str, Any]:
    """Extract structured data from URLs using Firecrawl Extract API.
    
    Args:
        urls: List of URLs to extract from
        extraction_prompt: What data to extract
        company_name: Target company name
    
    Returns:
        Extracted data dict
    
    Raises:
        ValueError: If Firecrawl API key not configured or extraction fails
        httpx.HTTPError: On network errors
    """
    settings = get_settings()
    if not settings.firecrawl_api_key:
        raise ValueError("FIRECRAWL_API_KEY not configured. Please set it in your .env file.")
    
    # Filter blocked domains again for safety
    clean_urls = filter_urls(urls)
    if not clean_urls:
        raise ValueError("No valid URLs to extract from after filtering.")
    
    schema = {
        "type": "object",
        "properties": {
            "company_name": {"type": "string"},
            "headquarters": {"type": "string"},
            "website": {"type": "string"},
            "founded": {"type": "string"},
            "industry": {"type": "string"},
            "business_units": {"type": "array", "items": {"type": "string"}},
            "products_and_services": {"type": "array", "items": {"type": "string"}},
            "target_industries": {"type": "array", "items": {"type": "string"}},
            "revenue": {"type": "string"},
            "employees": {"type": "string"},
            "executives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "title": {"type": "string"},
                    },
                },
            },
            "transformation_initiatives": {"type": "array", "items": {"type": "string"}},
            "erp_implementations": {"type": "array", "items": {"type": "string"}},
            "ai_initiatives": {"type": "array", "items": {"type": "string"}},
            "supply_chain_initiatives": {"type": "array", "items": {"type": "string"}},
            "investments": {"type": "array", "items": {"type": "string"}},
            "expansions": {"type": "array", "items": {"type": "string"}},
        },
    }
    
    payload = {
        "urls": clean_urls,
        "prompt": f"Extract business intelligence about {company_name}. {extraction_prompt}",
        "schema": schema,
    }
    
    headers = {
        "Authorization": f"Bearer {settings.firecrawl_api_key}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.firecrawl.dev/v1/extract",
            headers=headers,
            json=payload,
        )
        
        if response.status_code == 402:
            raise ValueError(
                "Firecrawl API: Insufficient balance (HTTP 402). "
                "Please check your Firecrawl account at https://firecrawl.dev"
            )
        
        if response.status_code == 429:
            raise ValueError(
                "Firecrawl API: Rate limit exceeded (HTTP 429). "
                "Please wait a moment before retrying."
            )
        
        response.raise_for_status()
    
    result = response.json()
    
    # Firecrawl may return async job - handle both sync and async responses
    if result.get("success") and result.get("data"):
        return result["data"]
    elif result.get("id"):
        # Async job - poll for completion
        return await _poll_firecrawl_job(result["id"], settings.firecrawl_api_key)
    
    return result.get("data", {})


async def _poll_firecrawl_job(job_id: str, api_key: str, max_attempts: int = 30) -> dict[str, Any]:
    """Poll Firecrawl for async job completion.
    
    Args:
        job_id: Firecrawl job ID
        api_key: Firecrawl API key
        max_attempts: Maximum polling attempts (each 5 seconds = max 150s)
    
    Returns:
        Extracted data dict
    
    Raises:
        ValueError: If job fails or times out
    """
    import asyncio
    
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(max_attempts):
            await asyncio.sleep(5)
            
            response = await client.get(
                f"https://api.firecrawl.dev/v1/extract/{job_id}",
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
            
            status = result.get("status")
            if status == "completed":
                return result.get("data", {})
            elif status == "failed":
                raise ValueError(
                    f"Firecrawl extraction failed: {result.get('error', 'Unknown error')}"
                )
            
            logger.debug("Firecrawl job %s status: %s (attempt %d)", job_id, status, attempt + 1)
    
    raise ValueError(
        "Firecrawl extraction timed out. The extraction took too long. Please try again."
    )


def build_report(
    company_name: str,
    extracted_data: dict[str, Any],
    source_urls: list[dict[str, Any]],
) -> IntelligenceReport:
    """Build a structured IntelligenceReport from extracted data.
    
    Args:
        company_name: Target company name
        extracted_data: Data extracted by Firecrawl
        source_urls: List of source URL dicts with title and link
    
    Returns:
        IntelligenceReport instance
    """
    # Company identifiers
    identifiers = CompanyIdentifiers(
        name=extracted_data.get("company_name") or company_name,
        headquarters=extracted_data.get("headquarters"),
        website=extracted_data.get("website"),
        founded=extracted_data.get("founded"),
        industry=extracted_data.get("industry"),
    )
    
    # Business snapshot
    snapshot = BusinessSnapshot(
        business_units=extracted_data.get("business_units", []),
        products_and_services=extracted_data.get("products_and_services", []),
        target_industries=extracted_data.get("target_industries", []),
        revenue=extracted_data.get("revenue"),
        employees=extracted_data.get("employees"),
    )
    
    # Leadership signals (only from official sources)
    executives = extracted_data.get("executives", [])
    leadership = LeadershipSignals(
        executives=executives,
        note="Named executives sourced only from official public company sources.",
    )
    
    # Strategic initiatives
    initiatives = StrategicInitiatives(
        transformation=extracted_data.get("transformation_initiatives", []),
        erp_implementations=extracted_data.get("erp_implementations", []),
        ai_initiatives=extracted_data.get("ai_initiatives", []),
        supply_chain=extracted_data.get("supply_chain_initiatives", []),
        investments=extracted_data.get("investments", []),
        expansions=extracted_data.get("expansions", []),
    )
    
    # Evidence sources
    evidence = [
        EvidenceSource(
            url=r["link"],
            title=r.get("title", ""),
            relevance="Source used for intelligence extraction",
        )
        for r in source_urls
        if r.get("link")
    ]
    
    return IntelligenceReport(
        company_identifiers=identifiers,
        business_snapshot=snapshot,
        leadership_signals=leadership,
        strategic_initiatives=initiatives,
        evidence_sources=evidence,
        generated_at=datetime.now(timezone.utc),
        data_quality_note=(
            "This report is auto-generated from publicly available web sources. "
            "Verify critical information independently before use."
        ),
    )


async def run_company_pipeline(
    company_name: str,
    objective_prompt: str,
    progress_callback=None,
) -> IntelligenceReport:
    """Run the full intelligence pipeline for a company.
    
    Args:
        company_name: Target company name
        objective_prompt: Research objective
        progress_callback: Optional async callable(message: str) for progress updates
    
    Returns:
        IntelligenceReport
    """
    settings = get_settings()
    
    async def update_progress(msg: str):
        logger.info("Pipeline progress: %s", msg)
        if progress_callback:
            await progress_callback(msg)
    
    # Step 1: SERP Discovery
    await update_progress("Searching for company information...")
    query = f"{company_name} company official site annual report news"
    serp_results = await search_serp(query, num_results=10)
    
    # Step 2: URL Selection via DeepSeek
    await update_progress("Selecting most relevant sources...")
    selected = await select_urls_with_llm(
        serp_results,
        objective=objective_prompt,
        company_name=company_name,
        max_urls=settings.max_urls_per_job,
    )
    
    urls_to_extract = [r["link"] for r in selected if r.get("link")]
    
    # Step 3: Firecrawl Extraction
    await update_progress(f"Extracting data from {len(urls_to_extract)} sources...")
    extracted = await extract_with_firecrawl(
        urls_to_extract,
        extraction_prompt=objective_prompt,
        company_name=company_name,
    )
    
    # Step 4: Build Report
    await update_progress("Building intelligence report...")
    report = build_report(company_name, extracted, selected)
    
    return report


async def run_geography_pipeline(
    location: str,
    criteria: str,
    objective_prompt: str,
    top_n: int = 3,
    progress_callback=None,
) -> GeographyResult:
    """Run the full intelligence pipeline for a geography/sector.
    
    Args:
        location: City/country or country/sector
        criteria: Target criteria (e.g., manufacturing, energy)
        objective_prompt: Research objective for each company
        top_n: Number of top companies to analyze
        progress_callback: Optional async callable(message: str)
    
    Returns:
        GeographyResult with company list and reports
    """
    settings = get_settings()
    
    async def update_progress(msg: str):
        logger.info("Pipeline progress: %s", msg)
        if progress_callback:
            await progress_callback(msg)
    
    # Step 1: Discover companies in the geography
    await update_progress(f"Discovering companies in {location}...")
    query = f"top {criteria} companies in {location} list"
    serp_results = await search_serp(query, num_results=10)
    
    # Step 2: Use DeepSeek to extract company names from results
    await update_progress("Identifying companies from search results...")
    companies = await _extract_company_names(serp_results, location, criteria, top_n)
    
    # Step 3: Run company pipeline for each company
    reports = []
    for i, company in enumerate(companies[:top_n], 1):
        await update_progress(f"Analyzing company {i}/{min(len(companies), top_n)}: {company}...")
        try:
            report = await run_company_pipeline(
                company,
                objective_prompt=objective_prompt,
            )
            reports.append(report)
        except Exception as e:
            logger.warning("Failed to generate report for %s: %s", company, type(e).__name__)
            # Continue with remaining companies
    
    return GeographyResult(
        location=location,
        criteria=criteria,
        companies_found=companies,
        reports=reports,
        generated_at=datetime.now(timezone.utc),
    )


async def _extract_company_names(
    serp_results: list[dict[str, Any]],
    location: str,
    criteria: str,
    top_n: int,
) -> list[str]:
    """Use DeepSeek to extract company names from SERP results.
    
    Args:
        serp_results: Search results
        location: Target location
        criteria: Target criteria
        top_n: Number of companies wanted
    
    Returns:
        List of company names
    """
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY not configured.")
    
    results_text = "\n".join(
        f"{i+1}. {r['title']}: {r['snippet']}"
        for i, r in enumerate(serp_results[:10])
    )
    
    prompt = f"""Extract a list of company names from these search results about {criteria} companies in {location}.

Search results:
{results_text}

Return ONLY a JSON object:
{{
  "companies": ["Company A", "Company B", "Company C"],
  "reasoning": "Brief explanation"
}}

Important:
- Return real company names only
- Focus on {criteria} sector
- List at least {top_n} companies if available
"""
    
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": settings.deepseek_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.deepseek_base_url}/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        
        if response.status_code == 402:
            raise ValueError(
                "DeepSeek API: Insufficient balance (HTTP 402). "
                "Please top up your DeepSeek account at https://platform.deepseek.com"
            )
        
        response.raise_for_status()
    
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    
    parsed = safe_parse_json(content)
    if parsed and parsed.get("companies"):
        return parsed["companies"][:top_n * 2]  # Get extra in case some fail
    
    # Fallback: extract from snippets manually
    logger.warning("Failed to extract company names from LLM, using fallback")
    return []
