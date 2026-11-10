import re
import time
from datetime import datetime, timedelta
from typing import Tuple, Optional
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
