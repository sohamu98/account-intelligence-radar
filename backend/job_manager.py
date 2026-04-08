"""APScheduler-based job manager for async intelligence pipeline execution."""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .models import JobStatus

logger = logging.getLogger(__name__)


class Job:
    """Represents a single intelligence pipeline job."""
    
    def __init__(self, job_id: str, job_type: str, params: dict[str, Any]):
        self.job_id = job_id
        self.job_type = job_type  # "company" or "geography"
        self.params = params
        self.status = JobStatus.QUEUED
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.progress: Optional[str] = None
        self.result: Optional[dict[str, Any]] = None
        self.error: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "message": self._get_message(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
        }
    
    def _get_message(self) -> str:
        messages = {
            JobStatus.QUEUED: "Job is queued and will start shortly.",
            JobStatus.PROCESSING: self.progress or "Processing intelligence pipeline...",
            JobStatus.COMPLETED: "Intelligence report generated successfully.",
            JobStatus.FAILED: f"Job failed: {self.error or 'Unknown error'}",
        }
        return messages.get(self.status, "Unknown status")


class JobManager:
    """Manages intelligence pipeline jobs with APScheduler."""
    
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()
        logger.info("JobManager initialized with APScheduler")
    
    def create_job(self, job_type: str, params: dict[str, Any]) -> str:
        """Create a new job and schedule it for immediate execution.
        
        Args:
            job_type: "company" or "geography"
            params: Job parameters
        
        Returns:
            job_id string
        """
        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id, job_type=job_type, params=params)
        self._jobs[job_id] = job
        
        # Schedule the job to run immediately
        self._scheduler.add_job(
            self._execute_job,
            args=[job_id],
            id=f"job_{job_id}",
            misfire_grace_time=60,
        )
        
        logger.info("Created job %s of type %s", job_id, job_type)
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID.
        
        Args:
            job_id: Job ID
        
        Returns:
            Job instance or None
        """
        return self._jobs.get(job_id)
    
    async def _execute_job(self, job_id: str):
        """Execute a job asynchronously.
        
        Args:
            job_id: Job ID to execute
        """
        job = self._jobs.get(job_id)
        if not job:
            logger.error("Job %s not found for execution", job_id)
            return
        
        job.status = JobStatus.PROCESSING
        job.updated_at = datetime.utcnow()
        
        async def progress_callback(msg: str):
            job.progress = msg
            job.updated_at = datetime.utcnow()
        
        try:
            from .pipeline import run_company_pipeline, run_geography_pipeline
            
            if job.job_type == "company":
                report = await run_company_pipeline(
                    company_name=job.params["company_name"],
                    objective_prompt=job.params["objective_prompt"],
                    progress_callback=progress_callback,
                )
                job.result = report.model_dump(mode="json")
            
            elif job.job_type == "geography":
                result = await run_geography_pipeline(
                    location=job.params["location"],
                    criteria=job.params["criteria"],
                    objective_prompt=job.params["objective_prompt"],
                    top_n=job.params.get("top_n", 3),
                    progress_callback=progress_callback,
                )
                job.result = result.model_dump(mode="json")
            
            job.status = JobStatus.COMPLETED
            job.updated_at = datetime.utcnow()
            logger.info("Job %s completed successfully", job_id)
        
        except ValueError as e:
            # User-facing errors (402, missing keys, no results, etc.)
            error_msg = str(e)
            job.status = JobStatus.FAILED
            job.error = error_msg
            job.updated_at = datetime.utcnow()
            logger.warning("Job %s failed with user error: %s", job_id, type(e).__name__)
        
        except Exception as e:
            # Unexpected errors - don't expose internals
            job.status = JobStatus.FAILED
            job.error = "An unexpected error occurred. Please check your API keys and try again."
            job.updated_at = datetime.utcnow()
            logger.error("Job %s failed with unexpected error: %s", job_id, type(e).__name__)
    
    def shutdown(self):
        """Gracefully shut down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("JobManager scheduler shut down")


# Global job manager instance
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get or create the global job manager instance."""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
