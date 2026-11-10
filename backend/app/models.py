from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any
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

class JobUpdateStatus(BaseModel):
    status: str
    notes: Optional[str] = None

class ScrapeRequest(BaseModel):
    # Support both list of roles and single string
    keywords: Union[List[str], str] = Field(default_factory=lambda: ["Python Developer"])
    locations: List[str] = Field(default_factory=lambda: ["Bengaluru"])
    open_to_all_india: bool = False
    sources: List[str] = Field(default_factory=lambda: ["linkedin", "indeed", "instahyre", "remoteok", "glassdoor"])
    results_per_source: int = 15
    is_remote: Optional[bool] = None
    date_posted_range: str = "7d" # "24h", "3d", "7d", "14d", "30d", "any"
    exp_ranges: List[str] = Field(default_factory=lambda: ["all"]) # e.g. ["0-1", "1-3"] or ["all"]
    exp_range: Optional[str] = "all" # legacy fallback
    linkedin_cookie: Optional[str] = ""
    naukri_cookie: Optional[str] = ""

class SchedulerConfig(BaseModel):
    enabled: bool = False
    interval_hours: float = 2.0
    scraper_config: Optional[ScrapeRequest] = None
