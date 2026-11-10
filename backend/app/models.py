from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
from datetime import datetime

class JobBase(BaseModel):
    id: str
    title: str
    company: str
    location: str
    is_remote: bool = False
    salary: Optional[str] = None
    experience: Optional[str] = None
    exp_min: Optional[int] = None
    exp_max: Optional[int] = None
    job_type: Optional[str] = "Full-time"
    source: str
    apply_url: str
    description: Optional[str] = None
    has_full_description: bool = False
    skills: List[str] = Field(default_factory=list)
    posted_date: Optional[str] = None
    posted_timestamp: Optional[int] = None
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "new"
    notes: Optional[str] = ""
    match_score: Optional[int] = None
    ai_score: Optional[int] = None
    ai_summary: Optional[str] = None
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    is_relevant: bool = False

class JobUpdateStatus(BaseModel):
    status: str
    notes: Optional[str] = None

class ScrapeRequest(BaseModel):
    keywords: Union[List[str], str] = Field(default_factory=lambda: ["Python Developer"])
    locations: List[str] = Field(default_factory=lambda: ["Bengaluru"])
    open_to_all_india: bool = False
    sources: List[str] = Field(default_factory=lambda: ["linkedin", "indeed", "instahyre", "remoteok", "glassdoor"])
    results_per_source: int = 15
    is_remote: Optional[bool] = None
    date_posted_range: str = "7d"
    exp_ranges: List[str] = Field(default_factory=lambda: ["all"])
    exp_range: Optional[str] = "all"
    linkedin_cookie: Optional[str] = ""
    naukri_cookie: Optional[str] = ""

class SchedulerConfig(BaseModel):
    enabled: bool = False
    interval_hours: float = 2.0
    scraper_config: Optional[ScrapeRequest] = None

class AIConfig(BaseModel):
    provider: str = "gemini" # "gemini" or "openai"
    api_key: str = ""
    model: Optional[str] = "gemini-1.5-flash"
    auto_filter_min_score: int = 70
    auto_evaluate_on_scrape: bool = True

class ResumeProfile(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    years_of_experience: Optional[int] = None
    skills: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
