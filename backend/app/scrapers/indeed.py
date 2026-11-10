from typing import List, Dict, Any
import hashlib
from jobspy import scrape_jobs
from app.scrapers.utils import parse_experience, parse_posted_timestamp

def generate_job_id(source: str, identifier: str) -> str:
    return hashlib.md5(f"{source}:{identifier}".encode()).hexdigest()

def scrape_indeed(
    keywords: str,
    location: str = "India",
    limit: int = 15,
    date_posted_range: str = "any",
    exp_range: str = "all"
) -> List[Dict[str, Any]]:
    """
    Scrapes Indeed jobs using JobSpy with TLS fingerprinting, experience parsing, and full descriptions.
    """
    jobs = []
    try:
        country = "india" if "india" in location.lower() or "bengaluru" in location.lower() or "delhi" in location.lower() or "pune" in location.lower() or "hyderabad" in location.lower() else "usa"
        
        hours_map = {
            "24h": 24,
            "3d": 72,
            "7d": 168,
            "14d": 336,
            "30d": 720
        }
        hours_old = hours_map.get(date_posted_range)

        df = scrape_jobs(
            site_name=["indeed"],
            search_term=keywords,
            location=location,
            results_wanted=limit,
            country_indeed=country,
            hours_old=hours_old
        )
        
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                title = str(row.get('title') or '').strip()
                company = str(row.get('company') or 'Unknown Company').strip()
                loc = str(row.get('location') or location).strip()
                url = str(row.get('job_url') or '')
                salary_min = row.get('min_amount')
                salary_max = row.get('max_amount')
                interval = row.get('interval')
                
                salary_str = None
                if salary_min or salary_max:
                    s_min = f"{int(salary_min):,}" if salary_min else ""
                    s_max = f"{int(salary_max):,}" if salary_max else ""
                    salary_str = f"{s_min} - {s_max} {interval or ''}".strip(" -")
                    
                is_remote = bool(row.get('is_remote')) or "remote" in title.lower() or "remote" in loc.lower()
                
                raw_id = url or f"{company}_{title}"
                job_id = generate_job_id("indeed", raw_id)
                
                desc = str(row.get('description') or '')
                has_full = len(desc) > 300
                
                posted_date = str(row.get('date_posted') or 'Recently')
                posted_timestamp = parse_posted_timestamp(posted_date)
                
                exp_min, exp_max = parse_experience(f"{title} {desc}")
                
                job_data = {
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "is_remote": is_remote,
                    "salary": salary_str,
                    "experience": f"{exp_min}-{exp_max} yrs" if (exp_min is not None and exp_max is not None) else None,
                    "exp_min": exp_min,
                    "exp_max": exp_max,
                    "job_type": str(row.get('job_type') or 'Full-time'),
                    "source": "indeed",
                    "apply_url": url,
                    "description": desc or f"Job posting on Indeed for {title} at {company}.",
                    "has_full_description": has_full,
                    "skills": [k.strip() for k in keywords.split() if len(k) > 2],
                    "posted_date": posted_date,
                    "posted_timestamp": posted_timestamp,
                    "status": "new"
                }
                jobs.append(job_data)
                if len(jobs) >= limit:
                    break
    except Exception as e:
        print(f"Error scraping Indeed: {e}")
        
    return jobs
