import requests
import hashlib
from typing import List, Dict, Any
from urllib.parse import quote_plus

def generate_job_id(source: str, identifier: str) -> str:
    return hashlib.md5(f"{source}:{identifier}".encode()).hexdigest()

def scrape_naukri(keywords: str, location: str = "India", limit: int = 15, session_cookie: str = "") -> List[Dict[str, Any]]:
    """
    Scrapes Naukri jobs.
    If session_cookie is provided (from a dummy or logged-in account), it fetches directly from Naukri API.
    Otherwise, it attempts guest search or gracefully falls back.
    """
    jobs = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "appid": "109",
        "systemid": "naukri",
        "clientid": "d3skt0p"
    }
    
    if session_cookie:
        headers["Cookie"] = session_cookie

    url = f"https://www.naukri.com/jobapi/v3/search?noOfResults={limit}&urlType=search_by_keyword&searchType=adv&keyword={quote_plus(keywords)}&location={quote_plus(location)}"

    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            job_details = data.get("jobDetails", [])
            for item in job_details:
                title = item.get("title", "")
                company = item.get("companyName", "Unknown")
                loc = ", ".join([l.get("label", "") for l in item.get("placeholders", []) if l.get("type") == "location"]) or location
                skills = [t.get("label") for t in item.get("tagsAndSkills", [])]
                static_url = item.get("staticUrl", "")
                if static_url and not static_url.startswith("http"):
                    apply_url = f"https://www.naukri.com{static_url}"
                else:
                    apply_url = static_url or f"https://www.naukri.com/job-listings-{item.get('jobId', '')}"
                
                exp_placeholder = next((l.get("label", "") for l in item.get("placeholders", []) if l.get("type") == "experience"), None)
                sal_placeholder = next((l.get("label", "") for l in item.get("placeholders", []) if l.get("type") == "salary"), None)
                
                job_id = generate_job_id("naukri", str(item.get("jobId") or f"{company}_{title}"))
                
                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "is_remote": "remote" in title.lower() or "remote" in loc.lower(),
                    "salary": sal_placeholder,
                    "experience": exp_placeholder,
                    "job_type": "Full-time",
                    "source": "naukri",
                    "apply_url": apply_url,
                    "description": item.get("jobDescription", f"Naukri listing for {title} at {company}"),
                    "skills": skills,
                    "posted_date": item.get("createdDate") or "Recently",
                    "status": "new"
                })
        else:
            print(f"Naukri returned status {res.status_code}. (Cookie needed if blocked by Akamai)")
    except Exception as e:
        print(f"Error scraping Naukri: {e}")

    return jobs
