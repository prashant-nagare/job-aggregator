import hashlib
from typing import List, Dict, Any
from jobspy import scrape_jobs

def generate_job_id(source: str, identifier: str) -> str:
    return hashlib.md5(f"{source}:{identifier}".encode()).hexdigest()

def scrape_glassdoor(keywords: str, location: str = "India", limit: int = 15) -> List[Dict[str, Any]]:
    """
    Scrapes Glassdoor jobs using JobSpy.
    """
    jobs = []
    try:
        df = scrape_jobs(
            site_name=["glassdoor"],
            search_term=keywords,
            location=location,
            results_wanted=limit
        )
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                title = str(row.get('title') or '').strip()
                company = str(row.get('company') or 'Unknown Company').strip()
                loc = str(row.get('location') or location).strip()
                url = str(row.get('job_url') or '')
                
                job_id = generate_job_id("glassdoor", url or f"{company}_{title}")
                is_remote = bool(row.get('is_remote')) or "remote" in title.lower() or "remote" in loc.lower()
                
                desc = str(row.get('description') or '')
                if len(desc) > 500:
                    desc = desc[:500] + "..."
                    
                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "is_remote": is_remote,
                    "salary": None,
                    "experience": None,
                    "job_type": str(row.get('job_type') or 'Full-time'),
                    "source": "glassdoor",
                    "apply_url": url,
                    "description": desc or f"View job opening at {company} on Glassdoor.",
                    "skills": [k.strip() for k in keywords.split() if len(k) > 2],
                    "posted_date": str(row.get('date_posted') or 'Recently'),
                    "status": "new"
                })
                if len(jobs) >= limit:
                    break
    except Exception as e:
        print(f"Error scraping Glassdoor: {e}")
        
    return jobs
