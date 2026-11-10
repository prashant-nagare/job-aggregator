import sqlite3
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "jobs.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        location TEXT NOT NULL,
        is_remote INTEGER DEFAULT 0,
        salary TEXT,
        experience TEXT,
        exp_min INTEGER,
        exp_max INTEGER,
        job_type TEXT DEFAULT 'Full-time',
        source TEXT NOT NULL,
        apply_url TEXT NOT NULL,
        description TEXT,
        has_full_description INTEGER DEFAULT 0,
        skills TEXT, -- JSON array
        posted_date TEXT,
        posted_timestamp INTEGER,
        scraped_at TEXT NOT NULL,
        status TEXT DEFAULT 'new', -- new, saved, applied, interviewing, offer, rejected
        notes TEXT DEFAULT '',
        match_score INTEGER
    );
    """)
    
    # Safe migration: add new columns if upgrading existing table
    cursor.execute("PRAGMA table_info(jobs)")
    columns = [row['name'] for row in cursor.fetchall()]
    
    new_cols = [
        ("exp_min", "INTEGER"),
        ("exp_max", "INTEGER"),
        ("posted_timestamp", "INTEGER"),
        ("has_full_description", "INTEGER DEFAULT 0")
    ]
    for col_name, col_type in new_cols:
        if col_name not in columns:
            cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")

    # Settings table for remembering scraper inputs & scheduler
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

def get_setting(key: str, default: Any = None) -> Any:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return default
    try:
        return json.loads(row['value'])
    except:
        return row['value']

def set_setting(key: str, value: Any) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    val_str = json.dumps(value) if not isinstance(value, str) else value
    cursor.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, val_str))
    conn.commit()
    conn.close()

def upsert_job(job: Dict[str, Any]) -> bool:
    """
    Inserts a new job or updates non-destructive fields if it exists.
    Preserves user status, notes, and full descriptions!
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, notes, has_full_description, description FROM jobs WHERE id = ?", (job['id'],))
    existing = cursor.fetchone()
    
    skills_json = json.dumps(job.get('skills', []))
    is_remote_int = 1 if job.get('is_remote') else 0
    scraped_at = job.get('scraped_at') or datetime.utcnow().isoformat()
    posted_timestamp = job.get('posted_timestamp') or int(time.time())
    exp_min = job.get('exp_min')
    exp_max = job.get('exp_max')

    if existing:
        # If existing already has a full description, don't overwrite it with a short snippet
        if existing['has_full_description'] and not job.get('has_full_description'):
            desc = existing['description']
            has_full = existing['has_full_description']
        else:
            desc = job.get('description') or existing['description']
            has_full = 1 if job.get('has_full_description') else existing['has_full_description']

        cursor.execute("""
            UPDATE jobs SET
                title = ?,
                company = ?,
                location = ?,
                is_remote = ?,
                salary = COALESCE(?, salary),
                experience = COALESCE(?, experience),
                exp_min = COALESCE(?, exp_min),
                exp_max = COALESCE(?, exp_max),
                job_type = COALESCE(?, job_type),
                apply_url = ?,
                description = ?,
                has_full_description = ?,
                skills = ?,
                posted_date = COALESCE(?, posted_date),
                posted_timestamp = COALESCE(?, posted_timestamp),
                scraped_at = ?
            WHERE id = ?
        """, (
            job['title'],
            job['company'],
            job['location'],
            is_remote_int,
            job.get('salary'),
            job.get('experience'),
            exp_min,
            exp_max,
            job.get('job_type'),
            job['apply_url'],
            desc,
            has_full,
            skills_json,
            job.get('posted_date'),
            posted_timestamp,
            scraped_at,
            job['id']
        ))
        conn.commit()
        conn.close()
        return False
    else:
        status = job.get('status', 'new')
        notes = job.get('notes', '')
        has_full = 1 if job.get('has_full_description') else 0
        cursor.execute("""
            INSERT INTO jobs (
                id, title, company, location, is_remote, salary, experience,
                exp_min, exp_max, job_type, source, apply_url, description,
                has_full_description, skills, posted_date, posted_timestamp,
                scraped_at, status, notes, match_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job['id'],
            job['title'],
            job['company'],
            job['location'],
            is_remote_int,
            job.get('salary'),
            job.get('experience'),
            exp_min,
            exp_max,
            job.get('job_type'),
            job['source'],
            job['apply_url'],
            job.get('description'),
            has_full,
            skills_json,
            job.get('posted_date'),
            posted_timestamp,
            scraped_at,
            status,
            notes,
            job.get('match_score')
        ))
        conn.commit()
        conn.close()
        return True

def update_job_description(job_id: str, description: str, exp_min: Optional[int] = None, exp_max: Optional[int] = None) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    if exp_min is not None or exp_max is not None:
        cursor.execute("""
            UPDATE jobs SET 
                description = ?, 
                has_full_description = 1,
                exp_min = COALESCE(?, exp_min),
                exp_max = COALESCE(?, exp_max)
            WHERE id = ?
        """, (description, exp_min, exp_max, job_id))
    else:
        cursor.execute("""
            UPDATE jobs SET description = ?, has_full_description = 1 WHERE id = ?
        """, (description, job_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d['is_remote'] = bool(d['is_remote'])
    d['has_full_description'] = bool(d.get('has_full_description', 0))
    try:
        d['skills'] = json.loads(d['skills']) if d['skills'] else []
    except:
        d['skills'] = []
    return d

def get_jobs(
    q: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    is_remote: Optional[bool] = None,
    locations: Optional[List[str]] = None,
    open_to_all_india: bool = False,
    date_range: Optional[str] = None,
    exp_min: Optional[int] = None,
    exp_max: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    
    if q:
        query += " AND (title LIKE ? OR company LIKE ? OR skills LIKE ? OR location LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term, term])
        
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
        
    if source and source != "all":
        query += " AND source = ?"
        params.append(source)
        
    if is_remote is not None:
        query += " AND is_remote = ?"
        params.append(1 if is_remote else 0)

    # Locations filter
    if not open_to_all_india and locations and len(locations) > 0 and locations != ["all"]:
        loc_clauses = []
        for loc in locations:
            if loc.strip():
                loc_clauses.append("location LIKE ?")
                params.append(f"%{loc.strip()}%")
        if loc_clauses:
            query += f" AND ({' OR '.join(loc_clauses)})"
    elif open_to_all_india:
        # Must match India or be remote or general
        query += " AND (location LIKE '%India%' OR is_remote = 1 OR location != '')"

    # Date range filter
    now_ts = int(time.time())
    date_deltas = {
        "24h": 86400,
        "3d": 259200,
        "7d": 604800,
        "14d": 1209600,
        "30d": 2592000
    }
    if date_range and date_range in date_deltas:
        threshold = now_ts - date_deltas[date_range]
        query += " AND (posted_timestamp IS NOT NULL AND posted_timestamp >= ?)"
        params.append(threshold)

    # Experience range filter
    if exp_min is not None:
        query += " AND (exp_max IS NULL OR exp_max >= ?)"
        params.append(exp_min)
    if exp_max is not None:
        query += " AND (exp_min IS NULL OR exp_min <= ?)"
        params.append(exp_max)
        
    query += " ORDER BY COALESCE(posted_timestamp, 0) DESC, scraped_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    results = []
    for r in rows:
        d = dict(r)
        d['is_remote'] = bool(d['is_remote'])
        d['has_full_description'] = bool(d.get('has_full_description', 0))
        try:
            d['skills'] = json.loads(d['skills']) if d['skills'] else []
        except:
            d['skills'] = []
        results.append(d)
        
    conn.close()
    return results

def update_job_status(job_id: str, status: str, notes: Optional[str] = None) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    if notes is not None:
        cursor.execute("UPDATE jobs SET status = ?, notes = ? WHERE id = ?", (status, notes, job_id))
    else:
        cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def delete_job(job_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def get_stats() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, count(*) as count FROM jobs GROUP BY status")
    status_counts = {r['status']: r['count'] for r in cursor.fetchall()}
    
    cursor.execute("SELECT source, count(*) as count FROM jobs GROUP BY source")
    source_counts = {r['source']: r['count'] for r in cursor.fetchall()}
    
    cursor.execute("SELECT count(*) as total FROM jobs")
    total = cursor.fetchone()['total']
    
    conn.close()
    return {
        "total": total,
        "by_status": status_counts,
        "by_source": source_counts
    }
