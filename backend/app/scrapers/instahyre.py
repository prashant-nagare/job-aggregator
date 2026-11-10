import requests
import hashlib
import time
from typing import List, Dict, Any
from urllib.parse import quote_plus
from app.scrapers.utils import parse_experience, parse_posted_timestamp, fetch_job_detail

def generate_job_id(source: str, identifier: str) -> str:
    return hashlib.md5(f"{source}:{identifier}".encode()).hexdigest()

def scrape_instahyre(
    keywords: str,
    location: str = "India",
    limit: int = 20,
    exp_range: str = "all",
    deep_scrape: bool = False
) -> List[Dict[str, Any]]:
    """
    Scrapes high-quality tech jobs from Instahyre with experience parsing and deep details.
    """
    jobs = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    url = f"https://www.instahyre.com/api/v1/job_search?query={quote_plus(keywords)}"
    if location and "india" not in location.lower() and "remote" not in location.lower():
        url += f"&locations={quote_plus(location)}"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            objects = data.get("objects", [])
            for item in objects:
                title = item.get("title") or item.get("candidate_title", "")
                employer = item.get("employer", {})
                company = employer.get("company_name", "Unknown")
                loc = item.get("locations") or location
                skills = item.get("keywords", [])
                public_url = item.get("public_url")
                if not public_url:
                    public_url = f"https://www.instahyre.com{item.get('resource_uri', '')}"
                
                note = employer.get("instahyre_note") or employer.get("company_tagline") or ""
                desc = f"{note}\n\nRequired Skills: {', '.join(skills)}" if skills else note
                has_full = False

                if deep_scrape and public_url:
                    full_desc = fetch_job_detail("instahyre", public_url)
                    if full_desc:
                        desc = full_desc
                        has_full = True

                # Parse experience
                exp_text = f"{title} {desc}"
                exp_min, exp_max = parse_experience(exp_text)
                
                # Check experience filter if specified
                if exp_range == "0-1" and exp_min is not None and exp_min > 1:
                    continue
                elif exp_range == "1-3" and exp_min is not None and exp_min > 3:
                    continue
                elif exp_range == "3-5" and exp_max is not None and exp_max < 3:
                    continue
                elif exp_range == "5-8" and exp_max is not None and exp_max < 5:
                    continue
                elif exp_range == "8+" and exp_max is not None and exp_max < 8:
                    continue

                raw_id = str(item.get("id") or f"{company}_{title}")
                job_id = generate_job_id("instahyre", raw_id)
                is_remote = "remote" in title.lower() or "remote" in str(loc).lower()

                # Estimated posted timestamp
                posted_timestamp = int(time.time()) - 86400 # Default ~1 day ago

                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "location": str(loc),
                    "is_remote": is_remote,
                    "salary": None,
                    "experience": f"{exp_min}-{exp_max} yrs" if (exp_min is not None and exp_max is not None) else None,
                    "exp_min": exp_min,
                    "exp_max": exp_max,
                    "job_type": "Full-time",
                    "source": "instahyre",
                    "apply_url": public_url,
                    "description": desc,
                    "has_full_description": has_full,
                    "skills": skills,
                    "posted_date": "Recently",
                    "posted_timestamp": posted_timestamp,
                    "status": "new"
                })
                if len(jobs) >= limit:
                    break
    except Exception as e:
        print(f"Error scraping Instahyre: {e}")

    return jobs
