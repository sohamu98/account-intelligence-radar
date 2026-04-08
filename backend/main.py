"""FastAPI application for Account Intelligence Radar."""
import csv
import io
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .config import get_settings
from .job_manager import JobManager, get_job_manager
from .models import (
    CompanyRequest,
    GeographyRequest,
    JobCreateResponse,
    JobStatus,
    JobStatusResponse,
)
from .utils import geography_result_to_markdown, report_to_csv_rows, report_to_markdown

# Configure logging - OWASP: do not log sensitive data
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    
    # Ensure reports directory exists
    os.makedirs(settings.reports_dir, exist_ok=True)
    logger.info("Application starting up")
    
    yield
    
    # Shutdown
    job_mgr = get_job_manager()
    job_mgr.shutdown()
    logger.info("Application shut down")


settings = get_settings()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="Production-grade business intelligence research tool for company discovery and analysis.",
    lifespan=lifespan,
)

# CORS - allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version}


@app.post("/api/jobs/company", response_model=JobCreateResponse)
async def submit_company_job(
    request: CompanyRequest,
    job_manager: JobManager = Depends(get_job_manager),
):
    """Submit a company intelligence research job.
    
    Creates an async job that runs the full pipeline:
    SerpAPI discovery → DeepSeek URL selection → Firecrawl extraction.
    """
    job_id = job_manager.create_job(
        job_type="company",
        params={
            "company_name": request.company_name,
            "objective_prompt": request.objective_prompt,
        },
    )
    
    return JobCreateResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message=f"Job created for company: {request.company_name}",
        created_at=datetime.utcnow(),
    )


@app.post("/api/jobs/geography", response_model=JobCreateResponse)
async def submit_geography_job(
    request: GeographyRequest,
    job_manager: JobManager = Depends(get_job_manager),
):
    """Submit a geography intelligence research job.
    
    Discovers companies in a location/sector and generates intelligence
    reports for the top N companies.
    """
    job_id = job_manager.create_job(
        job_type="geography",
        params={
            "location": request.location,
            "criteria": request.criteria,
            "objective_prompt": request.objective_prompt,
            "top_n": request.top_n,
        },
    )
    
    return JobCreateResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message=f"Job created for geography: {request.location} ({request.criteria})",
        created_at=datetime.utcnow(),
    )


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
):
    """Get job status and result.
    
    Poll this endpoint until status is 'completed' or 'failed'.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    
    return JobStatusResponse(**job.to_dict())


@app.get("/api/jobs/{job_id}/download/json")
async def download_job_json(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
):
    """Download job result as JSON file."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet.")
    
    content = json.dumps(job.result, indent=2, default=str)
    filename = f"intelligence_report_{job_id[:8]}.json"
    
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/jobs/{job_id}/download/markdown")
async def download_job_markdown(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
):
    """Download job result as Markdown file."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet.")
    
    result = job.result
    if not result:
        raise HTTPException(status_code=500, detail="No result data available.")
    
    # Check if it's a geography result or company result
    if "companies_found" in result:
        content = geography_result_to_markdown(result)
    else:
        content = report_to_markdown(result)
    
    filename = f"intelligence_report_{job_id[:8]}.md"
    
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/jobs/{job_id}/download/csv")
async def download_job_csv(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
):
    """Download job result as CSV file."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet.")
    
    result = job.result
    if not result:
        raise HTTPException(status_code=500, detail="No result data available.")
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if "companies_found" in result:
        # Geography result - write each company report
        reports = result.get("reports", [])
        for report in reports:
            rows = report_to_csv_rows(report)
            writer.writerows(rows)
            writer.writerow([])  # blank row between companies
    else:
        rows = report_to_csv_rows(result)
        writer.writerows(rows)
    
    filename = f"intelligence_report_{job_id[:8]}.csv"
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
