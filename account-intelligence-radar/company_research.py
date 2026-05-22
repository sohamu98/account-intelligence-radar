from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console

from src.config import Settings, load_settings
from src.discovery_serpapi import discover_urls_serpapi
from src.decision_openai import select_top_urls_openai, select_top_urls_heuristic
from src.extract_firecrawl import extract_company_facts_firecrawl
from src.extract_fallback import extract_company_facts_fallback
from src.reporting import write_report_files
from src.utils import ensure_dirs, sanitize_company_slug

console = Console()

DEFAULT_OBJECTIVE = (
    "Extract headquarters, business units, core products/services, target industries, "
    "key executives (official sources only), and recent strategic initiatives "
    "(transformation, ERP, AI, supply chain, data platforms, investments, expansions). "
    "Return structured JSON and include evidence links per claim."
)


def _unwrap_retry_error(err: Exception) -> Exception:
    root = err
    if hasattr(err, "last_attempt") and getattr(err.last_attempt, "exception", None):
        try:
            ex = err.last_attempt.exception()
            if ex:
                root = ex
        except Exception:
            root = err
    return root


def main() -> int:
    try:
        settings: Settings = load_settings()
    except Exception as e:
        console.print(f"[red]Config error:[/red] {e}")
        return 2

    ensure_dirs(settings)

    console.print("[bold]Account Intelligence Radar (Company Mode)[/bold]")
    company = console.input("Enter the company name: ").strip()
    if not company:
        console.print("[red]Company name is required.[/red]")
        return 2

    objective = console.input(
        "Enter what information you want about the company (press Enter for default): "
    ).strip()
    if not objective:
        objective = DEFAULT_OBJECTIVE
        console.print("[yellow]Using default objective prompt.[/yellow]")

    serp_query = company
    if company.lower() == "aramco":
        serp_query = "Saudi Aramco"

    run_ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    company_slug = sanitize_company_slug(company)
    out_dir = Path("reports") / f"{run_ts}_{company_slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[cyan]Searching Google via SerpAPI for:[/cyan] '{serp_query}' …")
    try:
        serp_results = discover_urls_serpapi(query=serp_query, settings=settings, limit=20)
    except Exception as e:
        console.print(f"[red]SerpAPI discovery failed:[/red] {e}")
        report = {
            "status": "error",
            "stage": "discovery",
            "company_input": company,
            "objective": objective,
            "error": str(e),
            "evidence": [],
        }
        write_report_files(out_dir=out_dir, company=company, report=report)
        return 1

    if not serp_results:
        console.print("[yellow]No SERP results found.[/yellow]")
        report = {
            "status": "no_results",
            "stage": "discovery",
            "company_input": company,
            "objective": objective,
            "evidence": [],
        }
        write_report_files(out_dir=out_dir, company=company, report=report)
        return 0

    console.print(f"[green]Found {len(serp_results)} candidate results.[/green]")

    console.print("\n[cyan]Selecting top 5 URLs via OpenAI…[/cyan]")
    try:
        selected = select_top_urls_openai(
            company=company,
            objective=objective,
            serp_results=serp_results,
            settings=settings,
            k=5,
        )
    except Exception as e:
        root = _unwrap_retry_error(e)
        console.print(f"[yellow]OpenAI selection failed, using heuristic fallback:[/yellow] {root}")
        selected = select_top_urls_heuristic(serp_results=serp_results, k=5)

    if not selected:
        console.print("[red]Could not select URLs for extraction.[/red]")
        report = {
            "status": "error",
            "stage": "decision",
            "company_input": company,
            "objective": objective,
            "error": "No URLs selected",
            "evidence": [],
        }
        write_report_files(out_dir=out_dir, company=company, report=report)
        return 1

    console.print("[bold]Selected URLs for extraction:[/bold]")
    for item in selected:
        console.print(f"- {item['url']}")

    urls = [x["url"] for x in selected]

    console.print("\n[cyan]Extracting structured data…[/cyan]")
    try:
        console.print("[cyan]Using Firecrawl…[/cyan]")
        report = extract_company_facts_firecrawl(
            company=company,
            objective=objective,
            selected_urls=urls,
            settings=settings,
        )
        report["status"] = "ok"
        report["company_input"] = company
        report["objective"] = objective
        report["selected_urls"] = selected
        report["extraction_mode"] = "firecrawl"
    except Exception as e:
        root = _unwrap_retry_error(e)
        console.print(f"[yellow]Firecrawl failed, switching to fallback extractor:[/yellow] {root}")

        # Fallback extractor (no credits needed)
        report = extract_company_facts_fallback(
            company=company,
            objective=objective,
            selected_urls=urls,
            settings=settings,
            max_pages=2,
        )
        report["status"] = "ok"
        report["company_input"] = company
        report["objective"] = objective
        report["selected_urls"] = selected
        report["extraction_mode"] = "fallback_no_firecrawl"

    write_report_files(out_dir=out_dir, company=company, report=report)
    console.print(f"\n[green]Saved report to:[/green] {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())