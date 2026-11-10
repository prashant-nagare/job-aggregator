# ⚡ JobScout Pro — Multi-Portal Job Aggregator & Application Tracker

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind-3.0%2B-38B2AC?logo=tailwind-css&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)

**A unified, multi-portal job scraping engine, deduplicator, and application tracker designed to help you search, filter, and apply across major job boards in seconds.**

[Features](#-key-features) • [Architecture](#-architecture--how-it-works) • [Quick Start](#-quick-start) • [Scraper Engine](#-scraper-engines--anti-bot-handling) • [API Reference](#-api-reference)

</div>

---

## 📌 The Problem It Solves

Applying for jobs across multiple portals (**LinkedIn**, **Instahyre**, **Indeed**, **RemoteOK**, **Glassdoor**, **Naukri**) requires maintaining dozens of browser tabs, repeatedly adjusting filters, dealing with duplicate postings, and manually logging application stages in spreadsheets.

**JobScout Pro solves this by:**
1. Scraping and aggregating listings from multiple portals in parallel.
2. Deduplicating identical roles across sites using normalized fuzzy matching.
3. Automatically parsing experience levels and posted date timestamps.
4. Scraping complete job descriptions from individual listing pages on demand.
5. Tracking application progress from **New ➔ Bookmarked ➔ Applied ➔ Interviewing ➔ Offer ➔ Rejected** in a Kanban pipeline.
6. Offering an **automated background scraper that checks for new listings every 2 hours**.

---

## 🚀 Key Features

### 1. Resume Matching & Candidate Profile (Manual Editor, AI & Offline)
* **✏️ Manual Profile & Skill Editor**:
  * Directly define your primary title, headline, experience years, notice period, and preferred roles.
  * Tag-based exact skill chips, tools breakdown with years of experience, and certifications (e.g. CEH).
  * 100% private: Zero personal contact details (no phone, no email, no address, no DOB) are ever requested or stored.
  * Includes a **`[🗑️ Clear Form]`** button to wipe inputs anytime.
* **📄 PDF Resume Upload**: Directly upload your resume PDF (parsed on the fly via `pypdf`).
* **Dual Parsing Methods (Selectable with 1 Click)**:
  * **🤖 AI Analysis**: Uses Gemini (`gemini-1.5-flash`) or OpenAI (`gpt-4o-mini`) for deep semantic extraction of experience, skills taxonomy, and executive summary.
  * **⚡ Offline Heuristic Method**: 100% private, instant rule-based keyword & pattern matcher. Operates locally with **zero API calls** and zero data sent externally.
  * Switch between AI and Offline analysis with one click anytime without re-uploading your PDF!
* **Match Score & Assessment (0 - 100%)**:
  * Evaluates technical skill overlap, seniority alignment, and domain relevance.
  * Identifies **Matched Skills** (green badges) and **Missing Skills** (orange warning tags) for each job.
  * Generates an honest 1-2 sentence AI verdict on your fit for the role.
* **Zero-Intervention Filtering**:
  * Filter jobs instantly by `🎯 Min Match: 60%+, 70%+, 80%+, 90%+`.
  * The 2-hour background auto-scraper automatically evaluates and scores all newly discovered listings against your profile!
* **Provider Flexibility**: Supports **Google Gemini** (`gemini-1.5-flash`, `gemini-2.0-flash`), **OpenAI** (`gpt-4o-mini`, `gpt-4o`), and offline heuristic matching.

### 2. Multi-Portal Live Scraping Engine
* **LinkedIn**: Uses LinkedIn's public guest job search endpoint (no credentials needed) + optional dummy account `li_at` cookie to bypass guest rate limits.
* **Instahyre**: Scrapes curated Indian tech openings (Adobe, Amazon, Swiggy, Flipkart, and funded startups) with clean skill tags and requirements.
* **Indeed**: TLS-fingerprinted browser sessions (`curl_cffi`) for anti-bot bypass.
* **RemoteOK**: Real-time worldwide remote engineering roles with salaries and tags.
* **Glassdoor**: Review-backed tech roles.
* **Naukri**: Session cookie support to bypass Akamai bot checkpoints with a dummy account.

### 2. Multi-Role & Multi-Location Targeting
* **Multi-Role Keywords (`+` Add Role)**: Add multiple target roles (e.g., `Python Developer`, `Backend Engineer`, `Full Stack Developer`) with quick suggestion chips.
* **Multi-Location Selection**: Pick one or more tech hubs (`Bengaluru`, `Hyderabad`, `Pune`, `Delhi NCR`, `Mumbai`, `Chennai`, `Remote`) or add custom cities.
* **🇮🇳 Open to All (India)**: One-click nationwide search across all locations in India without city constraints.

### 3. Date Posted & Experience Filtering
* **Date Posted Range**: Query and filter jobs posted within `Last 24 Hours`, `3 Days`, `7 Days`, `14 Days`, or `30 Days`.
* **Experience Range Buckets**: Multi-select seniority levels (`0-1 yrs Fresher`, `1-3 yrs Junior`, `3-5 yrs Mid-level`, `5-8 yrs Senior`, `8+ yrs Lead/Architect`).
* **Regex Experience Parser**: Extracts required years of experience from job titles and descriptions into structured `exp_min` and `exp_max` fields.

### 4. Deep Job Details Scraping
* Automatically scrapes full, detailed descriptions, responsibilities, and qualifications from the original job listing page on demand.
* Interactive slide-out drawer displays formatted descriptions, skill badges, and a **"🔄 Re-fetch Details"** button.

### 5. Automated Background Scraper (Every 2 Hours)
* Built-in asynchronous background scheduler runs every 2 hours to discover fresh postings.
* Simple **ON / OFF** toggle in the navigation bar with real-time countdown to the next run and summary statistics.
* Runs independently in the background without blocking the UI.

### 6. Application Tracker & Productivity Tools
* **Dual View Modes**:
  * **Feed View**: Cards with platform color badges, location tags, salary indicators, skills, and direct status toggles.
  * **Kanban Board**: Move jobs across stages (`New`, `Saved`, `Applied`, `Interviewing`, `Offer`, `Rejected`, `Not Relevant`).
* **⚡ Bulk Actions Bar**:
  * Select multiple or all visible jobs with checkboxes.
  * Bulk change status with 1 click (`Applied`, `Bookmarked`, `Rejected`, `Not Relevant`).
  * Bulk delete unwanted job listings in one action.
* **⚡ 1-Click Quick Apply & Status Actions**:
  * "Apply" opens the official portal posting in a new tab and automatically moves the card to `Applied`.
  * Dedicated `🚫 Not Relevant` quick button right on each card next to `Rejected` and delete.
* **Notes & Follow-ups**: Add custom notes (interviewer details, referral contacts, salary discussion).
* **CSV Export**: One-click export to download all tracked listings.
* **Persistent Preferences**: Remembers all your keywords, locations, cookies, and filters across browser sessions.

### 7. External Job Ingestion & Ghost Job Liveness Checker (Adapted for India)
* **➕ Direct Job Ingestion (`+ Add Job`)**:
  * **Paste Job URL**: Directly paste job links from LinkedIn, Naukri, Instahyre, Indeed, Lever, Greenhouse, Workday, or company ATS portals. JobScout automatically scrapes the role description, checks link liveness, and matches it against your profile in seconds.
  * **Paste Raw Text / WhatsApp Message**: Tailored for the Indian market where top tech and cybersecurity opportunities are frequently circulated in WhatsApp/Telegram groups or direct recruiter emails. Paste any raw message, specify optional title/company, and JobScout ingests and scores it instantly.
* **🔍 Ghost Job Liveness Checker**:
  * Indian portals frequently leave dead listings online as "ghost jobs" to inflate active listing counts.
  * JobScout checks HTTP status (404/410) and scans for portal closing markers (*"no longer accepting applications"*, *"job has expired"*, *"this vacancy is closed"*).
  * 1-click **`[🔍 Check Liveness]`** in the job inspection drawer, with immediate badge updates (`⚠️ Expired` vs `✓ Verified Live`).
* **🎯 Priority Recommendation Badges**:
  * Instant fit verdict displayed on every card and inspection drawer:
    * `🟢 High Priority Apply` (≥ 70% match): Top technical alignment with core skills.
    * `🟡 Stretch / Consider` (50–69% match): Partial overlap; suitable for stretch applications.
    * `🔴 Skip / Low Fit` (< 50% match): Low profile alignment.
    * `⚠️ Expired / Closed`: Dead or inactive listing.
  * **`👻 Filter Ghosts` Toggle**: 1-click toolbar button to hide all expired and closed listings from your feed.

---

## 🏗 Architecture & How It Works

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Target Job Portals                            │
│   LinkedIn   │   Instahyre   │   Indeed   │   RemoteOK   │  Glassdoor  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Parallel Scraping Layer (FastAPI)                    │
│   - ThreadPoolExecutor across Roles x Locations x Portals              │
│   - TLS Fingerprinting (curl_cffi) & Guest API Endpoints               │
│   - Relative Date & Experience Regex Extraction                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 Deduplication & Normalization Engine                   │
│   - Normalizes titles, company names & locations                       │
│   - Merges identical multi-posted listings                             │
│   - Preserves user application status & custom notes                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       Storage Layer (SQLite)                           │
│   - jobs.db (Persistent storage for jobs, statuses, and notes)         │
│   - settings (Remembers user inputs & scheduler state)                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Single-Port Dashboard UI (React 18 + Tailwind)            │
│   - Scraper Control Panel with + buttons for Roles & Experience        │
│   - Live Search, Date Posted & Seniority Filters                       │
│   - Kanban Pipeline Board & 1-Click Quick Apply                        │
│   - Dynamic Detail Page Scraper Drawer                                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠 Project Structure

```
job-aggregator/
├── run.sh                     # One-click startup script (default port: 8050)
├── requirements.txt           # Python backend dependencies
├── README.md                  # Comprehensive documentation
└── backend/
    ├── jobs.db                # SQLite database (auto-generated, git-ignored)
    └── app/
        ├── main.py            # FastAPI application & REST endpoints
        ├── models.py          # Pydantic data schemas & request models
        ├── database.py        # SQLite persistence, queries & migrations
        ├── scheduler.py       # Asynchronous 2-hour auto-scraper engine
        ├── static/
        │   └── index.html     # React 18 + Tailwind CSS dark-mode dashboard
        └── scrapers/
            ├── __init__.py
            ├── utils.py       # Date parser, experience regex, detail fetcher
            ├── aggregator.py  # Parallel orchestrator & deduplicator
            ├── linkedin.py    # LinkedIn guest + session cookie scraper
            ├── instahyre.py   # Instahyre tech jobs scraper
            ├── indeed.py      # Indeed scraper with TLS spoofing
            ├── remoteok.py    # RemoteOK API scraper
            ├── glassdoor.py   # Glassdoor scraper
            └── naukri.py      # Naukri scraper with session cookie support
```

---

## 🏁 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/prashant-nagare/job-aggregator.git
cd job-aggregator
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Application
Run the startup script:
```bash
./run.sh
```

Or start directly with Python:
```bash
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8050 --reload
```

### 4. Open the Web Dashboard
Navigate to:
```
http://localhost:8050
```

---

## 🌐 Scraper Engines & Anti-Bot Handling

Job portals implement strict anti-bot mechanisms. Here is how JobScout Pro handles each:

| Portal | Authentication Required? | Anti-Bot Bypass Strategy |
| :--- | :---: | :--- |
| **LinkedIn** | **No** (Public Guest API) | Queries LinkedIn's guest search endpoint. If guest rate limits occur (HTTP 429), an optional dummy account `li_at` cookie can be passed via the UI to bypass limits. |
| **Instahyre** | **No** | Direct REST API queries for candidate opportunities + `curl_cffi` browser impersonation (`chrome120`) to extract full listing descriptions without triggering Cloudflare blocks. |
| **Indeed** | **No** | Uses `jobspy` and `curl_cffi` to mimic standard Chrome TLS fingerprints, extracting markdown descriptions and salary metadata. |
| **RemoteOK** | **No** | Direct JSON API consumption with full HTML descriptions, tags, and timestamps. |
| **Glassdoor** | **No** | Automated scraper via JobSpy. |
| **Naukri** | Optional Session Cookie | Naukri uses Akamai Bot Manager (HTTP 406). Provide a session cookie from a dummy account in the UI's **"Dummy Account & Session Cookies"** section to scrape Naukri search directly. |

---

## 📡 API Reference

JobScout Pro provides a full REST API for programmatic access:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the web dashboard UI |
| `GET` | `/api/health` | Health check endpoint |
| `GET` | `/api/stats` | Summary statistics (total jobs, by status, by source) |
| `GET` | `/api/jobs` | Query listings with filters (`q`, `status`, `source`, `locations`, `open_to_all_india`, `date_range`, `exp_range`, `limit`, `offset`) |
| `GET` | `/api/jobs/{id}/details` | On-demand detail scraper: extracts and caches complete job description |
| `PATCH` | `/api/jobs/{id}/status` | Update job status (`new`, `saved`, `applied`, `interviewing`, `offer`, `rejected`, `not_relevant`) and custom notes |
| `POST` | `/api/jobs/bulk-status` | Bulk update status for multiple jobs in a single request |
| `DELETE` | `/api/jobs/{id}` | Remove a single listing |
| `POST` | `/api/jobs/bulk-delete` | Bulk delete multiple job listings in one action |
| `POST` | `/api/jobs/import` | Ingest external job from URL (LinkedIn, Naukri, ATS) or raw text (WhatsApp/Telegram) and calculate match score |
| `POST` | `/api/jobs/{id}/check-liveness` | Verify if job URL is active or expired/closed (Ghost Job checker) |
| `POST` | `/api/resume/manual` | Save structured manual profile and match criteria (100% private) |
| `POST` | `/api/resume/upload` | Upload resume PDF with selectable AI (`gemini`/`openai`) or offline local heuristic parsing |
| `POST` | `/api/jobs/{id}/evaluate` | Re-score an individual job against candidate profile |
| `POST` | `/api/jobs/evaluate-all` | Re-score entire database against profile |
| `POST` | `/api/scrape` | Trigger an on-demand multi-portal scrape and update configuration |
| `GET` | `/api/config` | Retrieve saved user scraper inputs |
| `POST` | `/api/config` | Save user scraper inputs |
| `GET` | `/api/scheduler/status` | Current status of 2-hour auto-scraper (enabled, next run, last result) |
| `POST` | `/api/scheduler/toggle` | Turn auto-scraper **ON** or **OFF** |
| `POST` | `/api/scheduler/run-now` | Trigger a scheduled run immediately |
| `GET` | `/api/export` | Download jobs as a CSV spreadsheet |

---

## 💡 How to Obtain Dummy Account Cookies (Optional)

You **do not need any account** to use JobScout Pro. However, if you want deep Naukri scraping or heavy LinkedIn volume:

1. **LinkedIn (`li_at`)**:
   - Open Chrome/Firefox DevTools (`F12`).
   - Go to **Application** ➔ **Cookies** ➔ `https://www.linkedin.com`.
   - Copy the value of the `li_at` cookie and paste it into the UI's **"Dummy Account & Session Cookies"** section.
2. **Naukri**:
   - Log into a dummy account on Naukri in your browser.
   - In DevTools ➔ **Network** tab, inspect any request to `naukri.com` and copy the `Cookie` header string.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
