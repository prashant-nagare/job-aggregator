import re
import time
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any
import requests
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

def parse_experience(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Extracts (min_years, max_years) from title, description, or experience string.
    Examples:
      "3-5 years" -> (3, 5)
      "5+ yrs" -> (5, None)
      "0 - 2 Years" -> (0, 2)
      "Fresher" -> (0, 1)
      "Lead 8+ years" -> (8, None)
    """
    if not text:
        return None, None
        
    t = text.lower()
    
    if "fresher" in t or "entry level" in t or "intern" in t:
        return 0, 1

    # Match range: e.g. "3 to 5 years", "3 - 5 yrs", "3-5 Yrs", "0-2"
    m_range = re.search(r'(\d+)\s*(?:-|–|to)\s*(\d+)\s*(?:yrs|years|yr)?', t)
    if m_range:
        try:
            return int(m_range.group(1)), int(m_range.group(2))
        except:
            pass

    # Match single minimum: e.g. "5+ years", "5+yrs", "min 3 years"
    m_plus = re.search(r'(\d+)\s*\+\s*(?:yrs|years|yr)?', t)
    if m_plus:
        try:
            return int(m_plus.group(1)), None
        except:
            pass

    m_min = re.search(r'(?:min|minimum|at least)\s*(\d+)\s*(?:yrs|years|yr)?', t)
    if m_min:
        try:
            return int(m_min.group(1)), None
        except:
            pass

    return None, None

def parse_posted_timestamp(posted_text: str) -> int:
    """
    Parses relative text into epoch timestamp seconds.
    Examples:
      "3 hours ago" -> now - 3*3600
      "2 days ago" -> now - 2*86400
      "1 week ago" -> now - 7*86400
      "1 month ago" -> now - 30*86400
    """
    now = int(time.time())
    if not posted_text:
        return now

    t = str(posted_text).lower().strip()

    if "just now" in t or "today" in t or "hour" in t or "minute" in t:
        # Check if hours mentioned: e.g. "4 hours ago"
        m_hr = re.search(r'(\d+)\s*hour', t)
        if m_hr:
            return now - (int(m_hr.group(1)) * 3600)
        return now

    m_day = re.search(r'(\d+)\s*day', t)
    if m_day:
        return now - (int(m_day.group(1)) * 86400)
    if "yesterday" in t:
        return now - 86400

    m_week = re.search(r'(\d+)\s*week', t)
    if m_week:
        return now - (int(m_week.group(1)) * 7 * 86400)

    m_month = re.search(r'(\d+)\s*month', t)
    if m_month:
        return now - (int(m_month.group(1)) * 30 * 86400)

    # Attempt to parse ISO / date format like "2026-11-08"
    try:
        dt = datetime.fromisoformat(t[:10])
        return int(dt.timestamp())
    except:
        pass

    return now

def fetch_job_detail(source: str, apply_url: str, raw_job_id: str = "") -> Optional[str]:
    """
    Scrapes the full detailed job description from the listing page.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    if source == "linkedin":
        # Extract LinkedIn Job ID from apply_url or raw_job_id
        # URLs look like https://in.linkedin.com/jobs/view/title-at-company-4468058393?...
        job_id = None
        if raw_job_id and raw_job_id.isdigit():
            job_id = raw_job_id
        else:
            m = re.search(r'-(\d{7,})(?:\?|$)', apply_url or "") or re.search(r'/view/(\d{7,})', apply_url or "")
            if m:
                job_id = m.group(1)

        if job_id:
            try:
                detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
                res = requests.get(detail_url, headers=headers, timeout=8)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    desc_div = soup.find("div", class_="show-more-less-html__markup")
                    if desc_div:
                        # Clean up html into readable text preserving linebreaks
                        for br in desc_div.find_all("br"):
                            br.replace_with("\n")
                        for p in desc_div.find_all(["p", "li"]):
                            p.append("\n")
                        return desc_div.text.strip()
            except Exception as e:
                print(f"Error fetching LinkedIn detail: {e}")

    elif source == "instahyre":
        if apply_url and cffi_requests:
            try:
                s = cffi_requests.Session(impersonate="chrome120")
                res = s.get(apply_url, timeout=10)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    desc_div = soup.find("div", class_="job-description") or soup.find("div", class_="description")
                    if desc_div:
                        for br in desc_div.find_all("br"):
                            br.replace_with("\n")
                        for p in desc_div.find_all(["p", "li"]):
                            p.append("\n")
                        return desc_div.text.strip()
            except Exception as e:
                print(f"Error fetching Instahyre detail: {e}")

    return None

def check_url_liveness(url: str) -> Dict[str, Any]:
    """
    Checks if a job listing URL is still active or expired/closed.
    Returns:
      is_live: bool
      is_expired: bool
      status: "active" | "expired" | "closed" | "unknown"
      reason: str
    """
    if not url or not url.startswith("http"):
        return {"is_live": True, "is_expired": False, "status": "unknown", "reason": "No valid URL to verify"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        if cffi_requests:
            session = cffi_requests.Session(impersonate="chrome120")
            res = session.get(url, headers=headers, timeout=12)
        else:
            res = requests.get(url, headers=headers, timeout=12)

        if res.status_code in [404, 410]:
            return {
                "is_live": False,
                "is_expired": True,
                "status": "expired",
                "reason": f"Page returned HTTP {res.status_code} (Removed)"
            }

        # Check page text for common closure / expiry signals
        text = res.text.lower()
        closed_signals = [
            "no longer accepting applications",
            "this job is closed",
            "job has expired",
            "this vacancy is no longer available",
            "position has been filled",
            "the job you are looking for is no longer active",
            "this posting has been removed",
            "job is not available",
            "this role is closed",
            "this job has expired",
            "posting is no longer active"
        ]

        for signal in closed_signals:
            if signal in text:
                return {
                    "is_live": False,
                    "is_expired": True,
                    "status": "closed",
                    "reason": f"Posting closed: '{signal.title()}'"
                }

        return {
            "is_live": True,
            "is_expired": False,
            "status": "active",
            "reason": "Posting is live and active"
        }
    except Exception as e:
        return {
            "is_live": True,
            "is_expired": False,
            "status": "unknown",
            "reason": f"Could not verify (Network/Anti-bot check): {e}"
        }

def parse_external_job_url(url: str) -> Dict[str, Any]:
    """
    Extracts structured job information from any URL (LinkedIn, Naukri, or direct company page).
    """
    if not url or not url.startswith("http"):
        raise ValueError("Invalid URL provided")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        if cffi_requests:
            session = cffi_requests.Session(impersonate="chrome120")
            res = session.get(url, headers=headers, timeout=15)
        else:
            res = requests.get(url, headers=headers, timeout=15)

        soup = BeautifulSoup(res.text, "html.parser")

        # 1. Title extraction
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # Clean title
        title = re.sub(r'\s*\|\s*(LinkedIn|Naukri|Indeed|Glassdoor).*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*(LinkedIn|Naukri|Indeed|Glassdoor).*$', '', title, flags=re.IGNORECASE)

        # 2. Company extraction
        company = "Direct Employer"
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content") and og_site["content"].lower() not in ["linkedin", "naukri", "indeed"]:
            company = og_site["content"].strip()
        
        m_at = re.search(r'(?:at|@)\s+([A-Za-z0-9\s&.,\-_]+)', title)
        if m_at:
            potential_company = m_at.group(1).strip()
            if len(potential_company) > 1 and len(potential_company) < 40:
                company = potential_company

        # 3. Location extraction
        location = "India"
        if "remote" in res.text.lower():
            location = "Remote / India"
        for city in ["Pune", "Bengaluru", "Bangalore", "Hyderabad", "Mumbai", "Delhi", "Gurgaon", "Gurugram", "Noida", "Chennai"]:
            if city.lower() in res.text.lower():
                location = city
                break

        # 4. Description extraction
        desc_el = (
            soup.find("div", class_=re.compile(r'description|jobDescription|job-description|details', re.I)) or
            soup.find("section", class_=re.compile(r'description|jobDescription', re.I)) or
            soup.find("article") or
            soup.find("main")
        )
        if desc_el:
            description = desc_el.get_text(separator="\n", strip=True)
        else:
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            description = soup.get_text(separator="\n", strip=True)

        if len(description) > 6000:
            description = description[:6000]

        exp_min, exp_max = parse_experience(f"{title} {description[:1000]}")

        source = "direct"
        if "linkedin.com" in url:
            source = "linkedin"
        elif "naukri.com" in url:
            source = "naukri"
        elif "instahyre.com" in url:
            source = "instahyre"
        elif "indeed.com" in url:
            source = "indeed"

        return {
            "title": title[:100] if title else "Job Opening",
            "company": company[:60],
            "location": location,
            "description": description,
            "apply_url": url,
            "source": source,
            "exp_min": exp_min,
            "exp_max": exp_max,
            "is_remote": "remote" in location.lower() or "remote" in title.lower()
        }
    except Exception as e:
        raise ValueError(f"Could not fetch or parse job from URL: {e}")
