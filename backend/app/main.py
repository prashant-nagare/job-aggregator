from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, FileResponse
from typing import Optional, List, Dict, Any
import io
import csv
import os
import asyncio

from app.models import JobBase, JobUpdateStatus, ScrapeRequest, SchedulerConfig
from app.database import (
    init_db, get_jobs, get_job_by_id, upsert_job, 
    update_job_status, update_job_description, delete_job, get_stats,
    get_setting, set_setting
)
from app.scrapers.aggregator import run_scraping_pipeline
from app.scrapers.utils import fetch_job_detail, parse_experience
from app.scheduler import scheduler

app = FastAPI(title="JobScout Aggregator API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.on_event("startup")
async def startup_event():
    init_db()
    scheduler.load_state()
    asyncio.create_task(scheduler.run_loop())

@app.get("/")
def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "JobScout Aggregator API is running. UI index not found."}

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "JobScout Aggregator"}

@app.get("/api/stats")
def get_dashboard_stats():
    return get_stats()

# Scraper configuration persistence (remember user inputs)
@app.get("/api/config")
def get_saved_config():
    config = get_setting("scraper_config", {
        "keywords": ["Python Developer"],
        "locations": ["Bengaluru"],
        "open_to_all_india": False,
        "date_posted_range": "7d",
        "exp_ranges": ["all"],
        "sources": ["linkedin", "indeed", "instahyre", "remoteok", "glassdoor"],
        "results_per_source": 15
    })
    return {"config": config}

@app.post("/api/config")
def save_config(request: ScrapeRequest):
    data = request.dict()
    set_setting("scraper_config", data)
    return {"status": "success", "message": "Scraper configuration saved", "config": data}

# Scheduler API
@app.get("/api/scheduler/status")
def get_scheduler_status():
    return scheduler.get_status()

@app.post("/api/scheduler/toggle")
def toggle_scheduler(payload: Dict[str, Any]):
    enable = bool(payload.get("enabled", False))
    config = payload.get("scraper_config")
    status = scheduler.toggle(enable, config)
    return {"status": "success", "scheduler": status}

@app.post("/api/scheduler/run-now")
async def trigger_scheduler_run_now(background_tasks: BackgroundTasks):
    background_tasks.add_task(scheduler.execute_scrape_job)
    return {"status": "success", "message": "Auto-scrape job started in background"}

@app.get("/api/jobs")
def list_jobs(
    q: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    is_remote: Optional[bool] = None,
    locations: Optional[str] = None,
    open_to_all_india: bool = Query(False),
    date_range: Optional[str] = Query(None),
    exp_range: Optional[str] = Query(None),
    min_exp: Optional[int] = Query(None),
    max_exp: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=300),
    offset: int = Query(0, ge=0)
):
    loc_list = [l.strip() for l in locations.split(",")] if locations else None
    
    exp_bounds = {
        "0-1": (0, 1),
        "1-3": (1, 3),
        "3-5": (3, 5),
        "5-8": (5, 8),
        "8+": (8, None)
    }
    calc_min_exp = min_exp
    calc_max_exp = max_exp
    if exp_range in exp_bounds:
        calc_min_exp, calc_max_exp = exp_bounds[exp_range]

    jobs = get_jobs(
        q=q,
        status=status,
        source=source,
        is_remote=is_remote,
        locations=loc_list,
        open_to_all_india=open_to_all_india,
        date_range=date_range,
        exp_min=calc_min_exp,
        exp_max=calc_max_exp,
        limit=limit,
        offset=offset
    )
    return {"jobs": jobs, "count": len(jobs)}

@app.get("/api/jobs/{job_id}/details")
def get_job_details(job_id: str):
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("has_full_description"):
        return {"id": job_id, "description": job["description"], "is_full": True}

    full_desc = fetch_job_detail(job["source"], job["apply_url"], job_id)
    if full_desc and len(full_desc) > 50:
        e_min, e_max = parse_experience(full_desc)
        update_job_description(job_id, full_desc, exp_min=e_min, exp_max=e_max)
        return {"id": job_id, "description": full_desc, "is_full": True, "exp_min": e_min, "exp_max": e_max}

    return {"id": job_id, "description": job["description"], "is_full": False}

@app.patch("/api/jobs/{job_id}/status")
def change_status(job_id: str, body: JobUpdateStatus):
    success = update_job_status(job_id, body.status, body.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job status updated successfully", "id": job_id, "status": body.status}

@app.delete("/api/jobs/{job_id}")
def remove_job(job_id: str):
    success = delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted successfully", "id": job_id}

@app.post("/api/scrape")
def trigger_scrape(request: ScrapeRequest):
    """
    Triggers live multi-portal scrape, saves configuration to remember user inputs,
    and returns aggregated job count.
    """
    # Remember configuration for next sessions and scheduler
    set_setting("scraper_config", request.dict())

    stats = run_scraping_pipeline(
        keywords=request.keywords,
        locations=request.locations,
        open_to_all_india=request.open_to_all_india,
        sources=request.sources,
        results_per_source=request.results_per_source,
        date_posted_range=request.date_posted_range,
        exp_ranges=request.exp_ranges,
        exp_range=request.exp_range or "all",
        naukri_cookie=request.naukri_cookie or "",
        linkedin_cookie=request.linkedin_cookie or ""
    )
    return {
        "status": "success",
        "message": f"Scraped {stats['total_scraped']} jobs ({stats['new_inserted']} new).",
        "details": stats
    }

@app.get("/api/export")
def export_jobs_csv(status: Optional[str] = None):
    jobs = get_jobs(status=status, limit=1000)
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "ID", "Title", "Company", "Location", "Is Remote", "Salary",
        "Experience", "Source", "Apply URL", "Status", "Notes", "Posted Date", "Scraped At"
    ])
    
    for j in jobs:
        writer.writerow([
            j.get("id"),
            j.get("title"),
            j.get("company"),
            j.get("location"),
            "Yes" if j.get("is_remote") else "No",
            j.get("salary") or "",
            j.get("experience") or "",
            j.get("source"),
            j.get("apply_url"),
            j.get("status"),
            j.get("notes") or "",
            j.get("posted_date") or "",
            j.get("scraped_at")
        ])
        
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs_export.csv"}
    )
