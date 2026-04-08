"""Configuration management using environment variables."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    serpapi_key: str = ""
    deepseek_api_key: str = ""
    firecrawl_api_key: str = ""
    
    # DeepSeek settings
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-reasoner"
    
    # App settings
    app_title: str = "Account Intelligence Radar"
    app_version: str = "1.0.0"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:80"]
    
    # Job settings
    job_timeout_seconds: int = 300
    max_urls_per_job: int = 5
    top_n_companies: int = 3
    
    # Reports directory
    reports_dir: str = "reports"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
