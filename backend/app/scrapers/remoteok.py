import requests
import hashlib
from typing import List, Dict, Any
from app.scrapers.utils import parse_experience, parse_posted_timestamp

def generate_job_id(source: str, identifier: str) -> str:
    return hashlib.md5(f"{source}:{identifier}".encode()).hexdigest()

def scrape_remoteok(
    keywords: str,
    limit: int = 15,
    date_posted_range: str = "any",
    exp_range: str = "all"
) -> List[Dict[str, Any]]:
    """
    Fetches real-time remote tech jobs from RemoteOK with rich descriptions and timestamps.
    """
    jobs = []
    try:
        url = "https://remoteok.com/api"
        headers = {
            "User-Agent": "JobAggregatorApp/1.0 (Mozilla/5.0 AppleWebKit/537.36)"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            keywords_lower = [k.lower().strip() for k in keywords.split() if len(k) > 1]
            
            for item in data:
                if not isinstance(item, dict) or "position" not in item:
                    continue
                
                position = item.get("position", "")
                tags = [t.lower() for t in item.get("tags", [])]
                company = item.get("company", "Unknown")
                
                text_to_search = f"{position} {' '.join(tags)} {company}".lower()
                matches = any(k in text_to_search for k in keywords_lower)
                
                if keywords_lower and not matches and "software" not in keywords_lower and "engineer" not in keywords_lower:
                    continue
                
                raw_id = item.get("id") or item.get("url") or f"{company}_{position}"
                job_id = generate_job_id("remoteok", str(raw_id))
                
                apply_url = item.get("url") or item.get("apply_url")
                if apply_url and not apply_url.startswith("http"):
                    apply_url = f"https://remoteok.com{apply_url}"
                    
                desc = item.get("description", "")
                posted_date = item.get("date", "Recently")[:10] if item.get("date") else "Recently"
                posted_timestamp = parse_posted_timestamp(item.get("date", ""))
                
                exp_min, exp_max = parse_experience(f"{position} {desc}")
                
                salary = None
                if item.get("salary_min") or item.get("salary_max"):
                    salary = f"${item.get('salary_min', 0):,} - ${item.get('salary_max', 0):,} USD"

                job_data = {
                    "id": job_id,
                    "title": position,
                    "company": company,
                    "location": item.get("location") or "Worldwide (Remote)",
                    "is_remote": True,
                    "salary": salary,
                    "experience": f"{exp_min}-{exp_max} yrs" if (exp_min is not None and exp_max is not None) else None,
                    "exp_min": exp_min,
                    "exp_max": exp_max,
                    "job_type": "Full-time",
                    "source": "remoteok",
                    "apply_url": apply_url,
                    "description": desc or f"Remote role for {position} at {company}",
                    "has_full_description": len(desc) > 200,
                    "skills": item.get("tags", []),
                    "posted_date": posted_date,
                    "posted_timestamp": posted_timestamp,
                    "status": "new"
                }
                jobs.append(job_data)
                if len(jobs) >= limit:
                    break
    except Exception as e:
        print(f"Error scraping RemoteOK: {e}")
        
    return jobs
