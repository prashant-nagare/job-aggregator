from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, FileResponse
from typing import Optional, List, Dict, Any
import io
import csv
import os
import asyncio
from datetime import datetime

from app.models import JobBase, JobUpdateStatus, BulkStatusRequest, BulkDeleteRequest, ScrapeRequest, SchedulerConfig, AIConfig
from app.database import (
    init_db, get_jobs, get_job_by_id, upsert_job, 
    update_job_status, bulk_update_status, update_job_description, update_job_ai_analysis,
    delete_job, bulk_delete_jobs, get_stats, get_setting, set_setting
)
from app.scrapers.aggregator import run_scraping_pipeline
from app.scrapers.utils import fetch_job_detail, parse_experience
from app.scheduler import scheduler
from app.ai_matcher import (
    extract_text_from_pdf, parse_resume_profile, 
    evaluate_job_match, batch_evaluate_unscored_jobs
)

app = FastAPI(title="JobScout Aggregator & AI Matcher API", version="1.3.0")

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

# AI Settings API (Gemini & OpenAI)
@app.get("/api/ai/config")
def get_ai_configuration():
    cfg = get_setting("ai_config", {
        "provider": "gemini",
        "api_key": "",
        "model": "gemini-1.5-flash",
        "auto_filter_min_score": 70,
        "auto_evaluate_on_scrape": True
    })
    # Mask API key for security
    masked_key = ""
    raw_key = cfg.get("api_key", "")
    if raw_key:
        masked_key = raw_key[:4] + "..." + raw_key[-4:] if len(raw_key) > 8 else "***"
    return {
        "provider": cfg.get("provider", "gemini"),
        "has_key": bool(raw_key),
        "masked_key": masked_key,
        "model": cfg.get("model", "gemini-1.5-flash"),
        "auto_filter_min_score": cfg.get("auto_filter_min_score", 70),
        "auto_evaluate_on_scrape": cfg.get("auto_evaluate_on_scrape", True)
    }

@app.post("/api/ai/config")
def save_ai_configuration(config: AIConfig):
    existing = get_setting("ai_config", {})
    # If user provided a masked key or empty, preserve existing key if available
    api_key = config.api_key.strip()
    if not api_key or "..." in api_key or "***" in api_key:
        api_key = existing.get("api_key", "")

    new_cfg = {
        "provider": config.provider,
        "api_key": api_key,
        "model": config.model,
        "auto_filter_min_score": config.auto_filter_min_score,
        "auto_evaluate_on_scrape": config.auto_evaluate_on_scrape
    }
    set_setting("ai_config", new_cfg)
    return {"status": "success", "message": "AI settings updated successfully", "provider": config.provider}

# Resume Management & PDF Upload
@app.post("/api/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    parse_method: str = Form("ai"),
    background_tasks: BackgroundTasks = None
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty PDF file uploaded.")

    try:
        extracted_text = extract_text_from_pdf(content)
        if not extracted_text or len(extracted_text.strip()) < 40:
            raise HTTPException(status_code=400, detail="Could not extract readable text from this PDF. Please ensure it's not a scanned image.")

        ai_cfg = get_setting("ai_config", {"provider": "gemini", "api_key": ""})
        profile = parse_resume_profile(
            resume_text=extracted_text,
            provider=ai_cfg.get("provider", "gemini"),
            api_key=ai_cfg.get("api_key", ""),
            model=ai_cfg.get("model", ""),
            parse_method=parse_method
        )

        resume_payload = {
            "filename": file.filename,
            "text": extracted_text,
            "profile": profile,
            "parse_method": parse_method,
            "updated_at": datetime.utcnow().isoformat()
        }
        set_setting("resume_data", resume_payload)

        # Automatically evaluate existing unscored jobs in background
        if background_tasks:
            def run_background_eval():
                unscored = get_jobs(limit=100)
                batch_evaluate_unscored_jobs(unscored, resume_payload, ai_cfg, force_method=parse_method, force_rescore=True)
            background_tasks.add_task(run_background_eval)

        return {
            "status": "success",
            "message": f"Resume '{file.filename}' analyzed successfully with {parse_method.upper()} method!",
            "profile": profile,
            "parse_method": parse_method
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF resume: {e}")

@app.post("/api/resume/manual")
async def save_manual_profile(payload: Dict[str, Any], background_tasks: BackgroundTasks = None):
    """
    Saves manually entered professional profile details without storing any private personal info.
    """
    target_title = (payload.get("target_title") or "").strip()
    headline = (payload.get("resume_headline") or "").strip()
    try:
        exp_years = float(payload.get("years_of_experience") or 0)
    except:
        exp_years = 0.0
    notice_period = (payload.get("notice_period") or "").strip()
    preferred_roles = [r.strip() for r in payload.get("preferred_roles", []) if r and r.strip()]
    skills = [s.strip() for s in payload.get("skills", []) if s and s.strip()]
    tools = payload.get("tools", [])
    summary = (payload.get("summary") or "").strip()
    experiences = payload.get("experiences", [])
    projects = payload.get("projects", [])
    certifications = [c.strip() for c in payload.get("certifications", []) if c and c.strip()]
    preferred_locations = [loc.strip() for loc in payload.get("preferred_locations", []) if loc and loc.strip()]

    # Generate searchable context for matchers
    text_parts = [
        f"Title: {target_title}",
        f"Headline: {headline}",
        f"Experience: {exp_years} years",
        f"Notice Period: {notice_period}",
        f"Preferred Roles: {', '.join(preferred_roles)}",
        f"Core Skills: {', '.join(skills)}",
        f"Certifications: {', '.join(certifications)}",
        f"Preferred Locations: {', '.join(preferred_locations)}",
        f"Professional Summary: {summary}"
    ]
    if tools:
        tool_strs = [f"{t.get('name')} ({t.get('experience_years', '')} yrs)" for t in tools if isinstance(t, dict) and t.get("name")]
        if tool_strs:
            text_parts.append(f"Tools & Tech: {', '.join(tool_strs)}")
    if experiences:
        text_parts.append("Work Experience:")
        for exp in experiences:
            if isinstance(exp, dict) and (exp.get("role") or exp.get("company")):
                text_parts.append(f"- {exp.get('role')} at {exp.get('company')} ({exp.get('duration')}): {exp.get('description')}")
    if projects:
        text_parts.append("Key Projects:")
        for proj in projects:
            if isinstance(proj, dict) and proj.get("title"):
                text_parts.append(f"- {proj.get('title')}: {proj.get('description')}")

    full_text = "\n".join(text_parts)

    profile_data = {
        "candidate_name": "Candidate Profile",
        "target_title": target_title,
        "resume_headline": headline,
        "years_of_experience": exp_years,
        "notice_period": notice_period,
        "preferred_roles": preferred_roles,
        "skills": skills,
        "tools": tools,
        "summary": summary,
        "experiences": experiences,
        "projects": projects,
        "certifications": certifications,
        "preferred_locations": preferred_locations,
        "domains": ["Cybersecurity", "IT Security", "Vulnerability Management"] if any("cyber" in s.lower() or "vulnerab" in s.lower() for s in skills) else ["Technology"],
        "parse_method": "manual"
    }

    resume_payload = {
        "filename": "Manual Professional Profile",
        "text": full_text,
        "profile": profile_data,
        "parse_method": "manual",
        "updated_at": datetime.utcnow().isoformat()
    }
    set_setting("resume_data", resume_payload)

    # Automatically score all jobs in background
    ai_cfg = get_setting("ai_config", {"provider": "gemini", "api_key": ""})
    eval_method = payload.get("eval_method", "offline" if not ai_cfg.get("api_key") else "ai")
    if background_tasks:
        def run_background_eval():
            all_jobs = get_jobs(limit=250)
            batch_evaluate_unscored_jobs(all_jobs, resume_payload, ai_cfg, force_method=eval_method, force_rescore=True)
        background_tasks.add_task(run_background_eval)

    return {
        "status": "success",
        "message": "Manual profile saved successfully and job scoring started!",
        "profile": profile_data,
        "parse_method": "manual"
    }

@app.post("/api/resume/reparse")
async def reparse_resume(payload: Dict[str, Any], background_tasks: BackgroundTasks = None):
    method = payload.get("parse_method", "ai")
    data = get_setting("resume_data")
    if not data or not data.get("text"):
        raise HTTPException(status_code=400, detail="No resume uploaded yet to re-analyze.")

    ai_cfg = get_setting("ai_config", {"provider": "gemini", "api_key": ""})
    profile = parse_resume_profile(
        resume_text=data["text"],
        provider=ai_cfg.get("provider", "gemini"),
        api_key=ai_cfg.get("api_key", ""),
        model=ai_cfg.get("model", ""),
        parse_method=method
    )

    data["profile"] = profile
    data["parse_method"] = method
    data["updated_at"] = datetime.utcnow().isoformat()
    set_setting("resume_data", data)

    # Re-evaluate jobs in background with new analysis
    if background_tasks:
        def run_background_eval():
            all_jobs = get_jobs(limit=250)
            batch_evaluate_unscored_jobs(all_jobs, data, ai_cfg, force_method=method, force_rescore=True)
        background_tasks.add_task(run_background_eval)

    return {
        "status": "success",
        "message": f"Resume re-analyzed using {method.upper()} method!",
        "profile": profile,
        "parse_method": method
    }

@app.get("/api/resume")
def get_current_resume():
    data = get_setting("resume_data")
    if not data:
        return {"has_resume": False}
    return {
        "has_resume": True,
        "filename": data.get("filename"),
        "profile": data.get("profile"),
        "parse_method": data.get("parse_method", "ai"),
        "updated_at": data.get("updated_at")
    }

@app.delete("/api/resume")
def delete_resume():
    set_setting("resume_data", None)
    return {"status": "success", "message": "Resume removed."}

# AI Job Evaluation Endpoints
@app.post("/api/jobs/{job_id}/evaluate")
def evaluate_single_job(job_id: str, method: str = Query("auto")):
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resume_data = get_setting("resume_data")
    if not resume_data or not resume_data.get("profile"):
        raise HTTPException(status_code=400, detail="Please upload your resume PDF first before running AI evaluation.")

    ai_cfg = get_setting("ai_config", {"provider": "gemini", "api_key": ""})
    eval_m = resume_data.get("parse_method", "ai") if method == "auto" else method

    res = evaluate_job_match(
        resume_profile=resume_data.get("profile", {}),
        resume_text=resume_data.get("text", ""),
        job=job,
        provider=ai_cfg.get("provider", "gemini"),
        api_key=ai_cfg.get("api_key", ""),
        model=ai_cfg.get("model", ""),
        eval_method=eval_m
    )

    update_job_ai_analysis(
        job_id=job_id,
        ai_score=res["match_score"],
        ai_summary=res["ai_summary"],
        matched_skills=res["matched_skills"],
        missing_skills=res["missing_skills"],
        is_relevant=res["is_relevant"]
    )
    return {"status": "success", "analysis": res}

@app.post("/api/jobs/evaluate-all")
async def evaluate_all_jobs(background_tasks: BackgroundTasks, method: str = Query("auto")):
    resume_data = get_setting("resume_data")
    if not resume_data or not resume_data.get("profile"):
        raise HTTPException(status_code=400, detail="Please upload your resume PDF first before evaluating.")

    ai_cfg = get_setting("ai_config", {"provider": "gemini", "api_key": ""})
    eval_m = resume_data.get("parse_method", "ai") if method == "auto" else method

    def run_eval():
        jobs = get_jobs(limit=250)
        batch_evaluate_unscored_jobs(jobs, resume_data, ai_cfg, force_method=eval_m, force_rescore=True)

    background_tasks.add_task(run_eval)
    return {"status": "success", "message": f"Analysis started in background for all job listings using {eval_m.upper()} method."}

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
    min_ai_score: Optional[int] = Query(None),
    only_relevant: bool = Query(False),
    limit: int = Query(60, ge=1, le=300),
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
        min_ai_score=min_ai_score,
        only_relevant=only_relevant,
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

@app.post("/api/jobs/bulk-status")
def change_status_bulk(body: BulkStatusRequest):
    updated = bulk_update_status(body.job_ids, body.status)
    return {"status": "success", "updated_count": updated, "new_status": body.status}

@app.delete("/api/jobs/{job_id}")
def remove_job(job_id: str):
    success = delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted successfully", "id": job_id}

@app.post("/api/jobs/bulk-delete")
def remove_jobs_bulk(body: BulkDeleteRequest):
    deleted = bulk_delete_jobs(body.job_ids)
    return {"status": "success", "deleted_count": deleted}

@app.post("/api/scrape")
def trigger_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Triggers live multi-portal scrape, saves configuration to remember user inputs,
    and automatically triggers AI evaluation if a resume is present.
    """
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

    # Trigger background evaluation on unscored jobs
    resume_data = get_setting("resume_data")
    ai_cfg = get_setting("ai_config", {"provider": "gemini", "api_key": ""})
    if resume_data and ai_cfg.get("auto_evaluate_on_scrape", True):
        def run_eval():
            unscored = get_jobs(limit=100)
            batch_evaluate_unscored_jobs(unscored, resume_data, ai_cfg)
        background_tasks.add_task(run_eval)

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
        "Experience", "AI Match Score", "AI Summary", "Source", "Apply URL", 
        "Status", "Notes", "Posted Date", "Scraped At"
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
            f"{j.get('ai_score')}%" if j.get("ai_score") is not None else "N/A",
            j.get("ai_summary") or "",
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
