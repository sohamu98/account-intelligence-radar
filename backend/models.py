"""Pydantic models for request/response validation."""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class InputMode(str, Enum):
    COMPANY = "company"
    GEOGRAPHY = "geography"


class CompanyRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    objective_prompt: str = Field(
        default="Extract headquarters, business units, core products, target industries, key executives, and recent strategic initiatives. Return structured JSON.",
        max_length=2000,
    )


class GeographyRequest(BaseModel):
    location: str = Field(..., min_length=1, max_length=200, description="City/country or country/sector")
    criteria: str = Field(..., min_length=1, max_length=500, description="Target criteria e.g. manufacturing, energy, logistics")
    objective_prompt: str = Field(
        default="Extract headquarters, business units, core products, target industries, key executives, and recent strategic initiatives. Return structured JSON.",
        max_length=2000,
    )
    top_n: int = Field(default=3, ge=1, le=10)


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime
    updated_at: datetime
    progress: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class CompanyIdentifiers(BaseModel):
    name: str
    headquarters: Optional[str] = None
    website: Optional[str] = None
    founded: Optional[str] = None
    industry: Optional[str] = None


class BusinessSnapshot(BaseModel):
    business_units: list[str] = []
    products_and_services: list[str] = []
    target_industries: list[str] = []
    revenue: Optional[str] = None
    employees: Optional[str] = None


class LeadershipSignals(BaseModel):
    executives: list[dict[str, str]] = []
    note: str = "Data sourced only from official public sources"


class StrategicInitiatives(BaseModel):
    transformation: list[str] = []
    erp_implementations: list[str] = []
    ai_initiatives: list[str] = []
    supply_chain: list[str] = []
    investments: list[str] = []
    expansions: list[str] = []
    other: list[str] = []


class EvidenceSource(BaseModel):
    url: str
    title: Optional[str] = None
    relevance: Optional[str] = None


class IntelligenceReport(BaseModel):
    company_identifiers: CompanyIdentifiers
    business_snapshot: BusinessSnapshot
    leadership_signals: LeadershipSignals
    strategic_initiatives: StrategicInitiatives
    evidence_sources: list[EvidenceSource] = []
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    data_quality_note: Optional[str] = None


class GeographyResult(BaseModel):
    location: str
    criteria: str
    companies_found: list[str] = []
    reports: list[IntelligenceReport] = []
    generated_at: datetime = Field(default_factory=datetime.utcnow)
