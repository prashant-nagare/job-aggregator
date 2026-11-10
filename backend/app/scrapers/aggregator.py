import concurrent.futures
import re
from typing import List, Dict, Any, Optional, Union
from app.scrapers.linkedin import scrape_linkedin
from app.scrapers.indeed import scrape_indeed
from app.scrapers.remoteok import scrape_remoteok
from app.scrapers.instahyre import scrape_instahyre
from app.scrapers.glassdoor import scrape_glassdoor
from app.scrapers.naukri import scrape_naukri
from app.database import upsert_job

def normalize_text(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '', (text or '').lower())

def is_duplicate(job_a: Dict[str, Any], job_b: Dict[str, Any]) -> bool:
    comp_a = normalize_text(job_a.get('company', ''))
    comp_b = normalize_text(job_b.get('company', ''))
    if comp_a and comp_b and comp_a == comp_b:
        title_a = normalize_text(job_a.get('title', ''))
        title_b = normalize_text(job_b.get('title', ''))
        if title_a == title_b or title_a in title_b or title_b in title_a:
            return True
    return False

def run_scraping_pipeline(
    keywords: Union[List[str], str] = "Software Engineer",
    locations: List[str] = None,
    open_to_all_india: bool = False,
    sources: List[str] = None,
    results_per_source: int = 15,
    date_posted_range: str = "any",
    exp_ranges: List[str] = None,
    exp_range: str = "all", # fallback
    deep_scrape: bool = False,
    naukri_cookie: str = "",
    linkedin_cookie: str = ""
) -> Dict[str, Any]:
    if not sources:
        sources = ["linkedin", "indeed", "instahyre", "remoteok", "glassdoor"]

    # Normalize keywords into a list of strings
    if isinstance(keywords, str):
        target_roles = [k.strip() for k in keywords.split(",") if k.strip()]
    elif isinstance(keywords, list):
        target_roles = [k.strip() for k in keywords if k.strip()]
    else:
        target_roles = ["Software Engineer"]
    if not target_roles:
        target_roles = ["Software Engineer"]

    # Determine location list
    if open_to_all_india or not locations or len(locations) == 0:
        target_locations = ["India"]
    else:
        target_locations = [loc.strip() for loc in locations if loc.strip()]
        if not target_locations:
            target_locations = ["India"]

    # Determine experience ranges
    if not exp_ranges or len(exp_ranges) == 0 or exp_ranges == ["all"]:
        active_exp_ranges = [exp_range if exp_range else "all"]
    else:
        active_exp_ranges = exp_ranges

    all_jobs = []
    source_stats = {src: 0 for src in sources}

    def fetch_source_task(src: str, loc: str, role: str, e_range: str):
        try:
            if src == "linkedin":
                return src, scrape_linkedin(
                    keywords=role,
                    location=loc,
                    limit=results_per_source,
                    session_cookie=linkedin_cookie,
                    date_posted_range=date_posted_range,
                    exp_range=e_range,
                    deep_scrape=deep_scrape
                )
            elif src == "indeed":
                return src, scrape_indeed(
                    keywords=role,
                    location=loc,
                    limit=results_per_source,
                    date_posted_range=date_posted_range,
                    exp_range=e_range
                )
            elif src == "instahyre":
                return src, scrape_instahyre(
                    keywords=role,
                    location=loc,
                    limit=results_per_source,
                    exp_range=e_range,
                    deep_scrape=deep_scrape
                )
            elif src == "remoteok":
                # RemoteOK only once per role
                if loc == target_locations[0] and e_range == active_exp_ranges[0]:
                    return src, scrape_remoteok(
                        keywords=role,
                        limit=results_per_source,
                        date_posted_range=date_posted_range,
                        exp_range=e_range
                    )
                return src, []
            elif src == "glassdoor":
                return src, scrape_glassdoor(
                    keywords=role,
                    location=loc,
                    limit=results_per_source
                )
            elif src == "naukri":
                return src, scrape_naukri(
                    keywords=role,
                    location=loc,
                    limit=results_per_source,
                    session_cookie=naukri_cookie
                )
            else:
                return src, []
        except Exception as e:
            print(f"Error fetching from {src} for {role} in {loc}: {e}")
            return src, []

    # Parallelize across sources, locations, roles, and experience ranges
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for role in target_roles:
            for loc in target_locations:
                for e_range in active_exp_ranges:
                    for src in sources:
                        tasks.append(executor.submit(fetch_source_task, src, loc, role, e_range))

        for future in concurrent.futures.as_completed(tasks):
            src, jobs = future.result()
            source_stats[src] = source_stats.get(src, 0) + len(jobs)
            all_jobs.extend(jobs)

    # In-memory deduplication across sources & locations
    unique_jobs = []
    for job in all_jobs:
        if not any(is_duplicate(job, u) for u in unique_jobs):
            unique_jobs.append(job)

    # Upsert into database
    new_count = 0
    updated_count = 0
    for job in unique_jobs:
        is_new = upsert_job(job)
        if is_new:
            new_count += 1
        else:
            updated_count += 1

    return {
        "total_scraped": len(all_jobs),
        "unique_scraped": len(unique_jobs),
        "new_inserted": new_count,
        "already_existing": updated_count,
        "by_source": source_stats
    }
