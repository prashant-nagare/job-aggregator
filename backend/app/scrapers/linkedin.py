import requests
from bs4 import BeautifulSoup
import re
import hashlib
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from app.scrapers.utils import parse_experience, parse_posted_timestamp, fetch_job_detail

def generate_job_id(source: str, identifier: str) -> str:
    return hashlib.md5(f"{source}:{identifier}".encode()).hexdigest()

def scrape_linkedin(
    keywords: str,
    location: str = "India",
    limit: int = 15,
    session_cookie: str = "",
    date_posted_range: str = "any",
    exp_range: str = "all",
    deep_scrape: bool = False
) -> List[Dict[str, Any]]:
    """
    Scrapes LinkedIn jobs using LinkedIn's public guest search endpoint.
    Supports date range filtering, experience filtering, and optional deep detail scraping.
    """
    jobs = []
    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    if session_cookie:
        headers["Cookie"] = session_cookie if "li_at=" in session_cookie else f"li_at={session_cookie}"

    # Build query params
    params = [
        f"keywords={quote_plus(keywords)}",
        f"location={quote_plus(location)}"
    ]

    # Date posted filter (f_TPR in seconds)
    tpr_map = {
        "24h": "r86400",
        "3d": "r259200",
        "7d": "r604800",
        "14d": "r1209600",
        "30d": "r2592000"
    }
    if date_posted_range in tpr_map:
        params.append(f"f_TPR={tpr_map[date_posted_range]}")

    # Experience level filter
    # 1: Internship, 2: Entry, 3: Associate, 4: Mid-Senior, 5: Director, 6: Executive
    exp_map = {
        "0-1": "1,2",
        "1-3": "2,3",
        "3-5": "3,4",
        "5-8": "4",
        "8+": "5,6"
    }
    if exp_range in exp_map:
        params.append(f"f_E={exp_map[exp_range]}")

    query_string = "&".join(params)
    start = 0

    while len(jobs) < limit and start < 60:
        url = f"{base_url}?{query_string}&start={start}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 429:
                print("LinkedIn rate limited (429).")
                break
            if res.status_code != 200:
                break
            
            soup = BeautifulSoup(res.text, "html.parser")
            job_cards = soup.find_all("li")
            if not job_cards:
                break

            for li in job_cards:
                title_elem = li.find("h3", class_="base-search-card__title")
                company_elem = li.find("h4", class_="base-search-card__subtitle")
                loc_elem = li.find("span", class_="job-search-card__location")
                link_elem = li.find("a", class_="base-card__full-link")
                time_elem = li.find("time")
                
                if not title_elem or not link_elem:
                    continue

                title = title_elem.text.strip()
                company = company_elem.text.strip() if company_elem else "Unknown Company"
                job_location = loc_elem.text.strip() if loc_elem else location
                apply_url = link_elem.get("href", "").split("?")[0]
                posted_date = time_elem.text.strip() if time_elem else "Recently"
                posted_timestamp = parse_posted_timestamp(posted_date)
                
                job_id_match = re.search(r"-(\d+)(?:\?|$)", apply_url)
                raw_id = job_id_match.group(1) if job_id_match else f"{company}_{title}"
                job_id = generate_job_id("linkedin", raw_id)
                
                is_remote = "remote" in title.lower() or "remote" in job_location.lower()
                exp_min, exp_max = parse_experience(f"{title} {keywords}")

                description = f"View full listing on LinkedIn for {title} at {company}."
                has_full = False

                if deep_scrape and raw_id.isdigit():
                    full_desc = fetch_job_detail("linkedin", apply_url, raw_id)
                    if full_desc:
                        description = full_desc
                        has_full = True
                        e_min, e_max = parse_experience(full_desc)
                        if e_min is not None:
                            exp_min, exp_max = e_min, e_max

                job_data = {
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "location": job_location,
                    "is_remote": is_remote,
                    "salary": None,
                    "experience": f"{exp_min}-{exp_max} yrs" if (exp_min is not None and exp_max is not None) else None,
                    "exp_min": exp_min,
                    "exp_max": exp_max,
                    "job_type": "Full-time",
                    "source": "linkedin",
                    "apply_url": apply_url,
                    "description": description,
                    "has_full_description": has_full,
                    "skills": [k.strip() for k in keywords.split() if len(k) > 2],
                    "posted_date": posted_date,
                    "posted_timestamp": posted_timestamp,
                    "status": "new"
                }
                jobs.append(job_data)
                if len(jobs) >= limit:
                    break

            start += len(job_cards)
        except Exception as e:
            print(f"Error scraping LinkedIn: {e}")
            break

    return jobs
