import io
import re
import json
from typing import Dict, Any, List, Optional
import requests
from pypdf import PdfReader
from app.database import update_job_ai_analysis

COMMON_TECH_SKILLS = [
    "python", "javascript", "typescript", "java", "golang", "c++", "c#", "rust",
    "react", "angular", "vue", "next.js", "node.js", "express", "django", "flask",
    "fastapi", "spring boot", "ruby", "rails", "php", "laravel",
    "sql", "postgresql", "mysql", "mongodb", "redis", "cassandra", "dynamodb",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd", "linux",
    "git", "graphql", "rest", "microservices", "kafka", "rabbitmq", "celery",
    "machine learning", "deep learning", "nlp", "llm", "pytorch", "tensorflow", "pandas"
]

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts text from a PDF file using pypdf.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts).strip()

def heuristic_profile_extraction(resume_text: str) -> Dict[str, Any]:
    """
    Fallback extractor using NLP/regex when no API key is set.
    """
    text_lower = resume_text.lower()
    
    # Extract matching tech skills
    found_skills = []
    for skill in COMMON_TECH_SKILLS:
        pattern = rf'\b{re.escape(skill)}\b'
        if re.search(pattern, text_lower):
            found_skills.append(skill.title() if len(skill) > 3 else skill.upper())

    # Extract years of experience
    exp_years = 2
    m_exp = re.search(r'(\d+)\s*\+?\s*(?:years|yrs)\s*(?:of\s*)?experience', text_lower)
    if m_exp:
        try:
            exp_years = int(m_exp.group(1))
        except:
            pass

    # Extract likely title from first 3 lines
    lines = [l.strip() for l in resume_text.split("\n") if len(l.strip()) > 3]
    candidate_name = lines[0] if lines else "Candidate"
    target_title = lines[1] if len(lines) > 1 else "Software Engineer"

    return {
        "candidate_name": candidate_name[:40],
        "target_title": target_title[:50],
        "years_of_experience": exp_years,
        "skills": found_skills[:25],
        "domains": ["Technology", "Software Development"],
        "summary": f"Software professional with ~{exp_years} years experience in {', '.join(found_skills[:5])}."
    }

def call_gemini(api_key: str, prompt: str, model: str = "gemini-1.5-flash") -> Optional[str]:
    """
    Calls Google Gemini REST API.
    """
    model_name = model or "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }
    res = requests.post(url, headers=headers, json=payload, timeout=20)
    if res.status_code == 200:
        data = res.json()
        candidates = data.get("candidates", [])
        if candidates:
            return candidates[0]["content"]["parts"][0]["text"]
    else:
        print(f"[Gemini API Error] {res.status_code}: {res.text[:200]}")
    return None

def call_openai(api_key: str, prompt: str, model: str = "gpt-4o-mini") -> Optional[str]:
    """
    Calls OpenAI REST API.
    """
    model_name = model or "gpt-4o-mini"
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model_name,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are an expert technical talent assessor. Always respond in valid JSON format."},
            {"role": "user", "content": prompt}
        ]
    }
    res = requests.post(url, headers=headers, json=payload, timeout=20)
    if res.status_code == 200:
        data = res.json()
        return data["choices"][0]["message"]["content"]
    else:
        print(f"[OpenAI API Error] {res.status_code}: {res.text[:200]}")
    return None

def parse_resume_profile(
    resume_text: str,
    provider: str = "gemini",
    api_key: str = "",
    model: str = ""
) -> Dict[str, Any]:
    """
    Uses Gemini, OpenAI, or heuristic fallback to parse a resume into structured profile.
    """
    if not api_key:
        return heuristic_profile_extraction(resume_text)

    prompt = f"""
    Analyze the following resume and extract the candidate profile in strict JSON:
    {{
      "candidate_name": "Full Name",
      "target_title": "Primary professional title / role",
      "years_of_experience": 4,
      "skills": ["Skill1", "Skill2", "Skill3"],
      "domains": ["Domain1", "Domain2"],
      "summary": "2-3 sentence executive summary of candidate strengths"
    }}

    RESUME:
    {resume_text[:4000]}
    """

    try:
        raw_json = None
        if provider == "gemini":
            raw_json = call_gemini(api_key, prompt, model)
        elif provider == "openai":
            raw_json = call_openai(api_key, prompt, model)

        if raw_json:
            clean = re.sub(r'^```json\s*', '', raw_json.strip())
            clean = re.sub(r'```$', '', clean.strip())
            return json.loads(clean)
    except Exception as e:
        print(f"Error parsing resume with LLM: {e}")

    return heuristic_profile_extraction(resume_text)

def evaluate_job_match(
    resume_profile: Dict[str, Any],
    resume_text: str,
    job: Dict[str, Any],
    provider: str = "gemini",
    api_key: str = "",
    model: str = ""
) -> Dict[str, Any]:
    """
    Evaluates how well a job posting matches the candidate's resume.
    Returns:
      match_score: int (0-100)
      is_relevant: bool
      matched_skills: list[str]
      missing_skills: list[str]
      ai_summary: str
    """
    job_desc = job.get("description") or ""
    job_title = job.get("title") or ""
    job_skills = job.get("skills") or []
    
    # If API key is present, use LLM
    if api_key:
        prompt = f"""
        You are an expert technical talent assessor and career matchmaker.
        Evaluate whether this job posting is a suitable match for the candidate based on their profile and resume.

        CANDIDATE PROFILE:
        - Target Role: {resume_profile.get('target_title', '')}
        - Years of Experience: {resume_profile.get('years_of_experience', 0)}
        - Core Skills: {', '.join(resume_profile.get('skills', []))}
        - Summary: {resume_profile.get('summary', '')}

        JOB POSTING:
        - Title: {job_title}
        - Company: {job.get('company')}
        - Location: {job.get('location')} (Remote: {job.get('is_remote')})
        - Experience Required: {job.get('experience', 'Not specified')}
        - Listed Skills: {', '.join(job_skills)}
        - Job Description Excerpt:
        {job_desc[:2500]}

        Return JSON matching this exact schema:
        {{
          "match_score": 85, // integer 0 to 100 based on technical skill fit, seniority match, and role alignment
          "is_relevant": true, // boolean, true if match_score >= 65
          "matched_skills": ["Skill1", "Skill2"], // skills the candidate has that match this role
          "missing_skills": ["Skill3"], // required skills mentioned in job that candidate may lack
          "ai_summary": "1-2 sentence concise explanation of why this job matches or what critical skill is missing"
        }}
        """

        try:
            raw_json = None
            if provider == "gemini":
                raw_json = call_gemini(api_key, prompt, model)
            elif provider == "openai":
                raw_json = call_openai(api_key, prompt, model)

            if raw_json:
                clean = re.sub(r'^```json\s*', '', raw_json.strip())
                clean = re.sub(r'```$', '', clean.strip())
                parsed = json.loads(clean)
                return {
                    "match_score": int(parsed.get("match_score", 50)),
                    "is_relevant": bool(parsed.get("is_relevant", False)),
                    "matched_skills": parsed.get("matched_skills", []),
                    "missing_skills": parsed.get("missing_skills", []),
                    "ai_summary": parsed.get("ai_summary", "Evaluation complete.")
                }
        except Exception as e:
            print(f"Error evaluating match with {provider}: {e}")

    # Fallback Heuristic Match Evaluator (Works offline / without API key!)
    candidate_skills = [s.lower() for s in resume_profile.get("skills", [])]
    text_to_search = f"{job_title} {job_desc} {' '.join(job_skills)}".lower()

    matched = []
    for s in resume_profile.get("skills", []):
        if re.search(rf'\b{re.escape(s.lower())}\b', text_to_search):
            matched.append(s)

    # Check job skills that candidate might be missing
    missing = []
    for js in job_skills:
        if not any(cs in js.lower() or js.lower() in cs for cs in candidate_skills):
            if len(js) > 2:
                missing.append(js)

    # Calculate score
    base_score = 40
    if matched:
        base_score += min(45, len(matched) * 12)
    # Check title alignment
    title_words = [w.lower() for w in job_title.split() if len(w) > 3]
    cand_title = (resume_profile.get("target_title") or "").lower()
    if any(w in cand_title for w in title_words):
        base_score += 15

    final_score = min(98, max(20, base_score))
    is_rel = final_score >= 65

    verdict = f"Matches {len(matched)} key skills ({', '.join(matched[:3])})." if matched else "Limited direct skill overlap detected."
    if missing:
        verdict += f" Missing: {', '.join(missing[:3])}."

    return {
        "match_score": final_score,
        "is_relevant": is_rel,
        "matched_skills": matched[:8],
        "missing_skills": missing[:6],
        "ai_summary": verdict
    }

def batch_evaluate_unscored_jobs(
    jobs: List[Dict[str, Any]],
    resume_data: Dict[str, Any],
    ai_config: Dict[str, Any]
) -> int:
    """
    Evaluates unscored jobs against the candidate's resume.
    """
    if not resume_data or not resume_data.get("profile"):
        return 0

    profile = resume_data.get("profile", {})
    resume_text = resume_data.get("text", "")
    provider = ai_config.get("provider", "gemini")
    api_key = ai_config.get("api_key", "")
    model = ai_config.get("model", "")

    count = 0
    for job in jobs:
        # Only evaluate if not yet scored
        if job.get("ai_score") is None:
            res = evaluate_job_match(profile, resume_text, job, provider, api_key, model)
            update_job_ai_analysis(
                job_id=job["id"],
                ai_score=res["match_score"],
                ai_summary=res["ai_summary"],
                matched_skills=res["matched_skills"],
                missing_skills=res["missing_skills"],
                is_relevant=res["is_relevant"]
            )
            count += 1

    return count
