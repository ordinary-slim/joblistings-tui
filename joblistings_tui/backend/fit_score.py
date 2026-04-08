import re
import pandas as pd

import logging as log

from .llm import get_client
from joblistings_tui.config import RESUME_MD

SCORE_PROMPT = """You are a job fit evaluator. Given a candidate's resume and a job description, score how well the candidate fits the role.

SCORING CRITERIA:
- 9-10: Perfect match. Candidate has direct experience in nearly all required skills and qualifications.
- 7-8: Strong match. Candidate has most required skills, minor gaps easily bridged.
- 5-6: Moderate match. Candidate has some relevant skills but missing key requirements.
- 3-4: Weak match. Significant skill gaps, would need substantial ramp-up.
- 1-2: Poor match. Completely different field or experience level.

IMPORTANT FACTORS:
- Weight technical skills heavily (programming languages, frameworks, tools)
- Consider transferable experience (automation, scripting, API work)
- Factor in the candidate's project experience
- Be realistic about experience level vs. job requirements (years of experience, seniority)

RESPOND IN EXACTLY THIS FORMAT (no other text):
SCORE: [1-10]
KEYWORDS: [comma-separated ATS keywords from the job description that match or could match the candidate]
REASONING: [2-3 sentences explaining the score]"""


def _parse_score_response(response: str) -> dict:
    """Parse the LLM's score response into structured data.

    Args:
        response: Raw LLM response text.

    Returns:
        {"score": int, "keywords": str, "reasoning": str}
    """
    score = 0
    keywords = ""
    reasoning = ""

    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("SCORE:"):
            try:
                match = re.search(r"\d+", line)
                if match is None:
                    raise ValueError("No numeric score found")
                score = int(match.group())
                score = max(1, min(10, score))
            except (AttributeError, ValueError):
                score = 0
        elif line.startswith("KEYWORDS:"):
            keywords = line.replace("KEYWORDS:", "").strip()
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()

    return {"score": score, "keywords": keywords, "reasoning": reasoning}


def score_job(
    job: dict,
    resume_text: str = "",
) -> dict:
    """Score a single job against the resume.

    Args:
        resume_text: The candidate's full resume text.
        job: Job dict with keys: title, site, location, description.

    Returns:
        {"score": int, "keywords": str, "reasoning": str}
    """
    job_text = (
        f"TITLE: {job['title']}\n"
        f"COMPANY: {job['company']}\n"
        f"LOCATION: {job.get('location', 'N/A')}\n\n"
        f"DESCRIPTION:\n{(job.get('description') or '')[:6000]}"
    )

    if not resume_text:
        try:
            with open(RESUME_MD, "r") as f:
                resume_text = f.read()
        except Exception as e:
            log.error("Error loading resume for scoring: %s", e)
            return {
                "score": 0,
                "keywords": "",
                "reasoning": f"Error loading resume: {e}",
            }

    messages = [
        {"role": "system", "content": SCORE_PROMPT},
        {
            "role": "user",
            "content": f"RESUME:\n{resume_text}\n\n---\n\nJOB POSTING:\n{job_text}",
        },
    ]

    try:
        client = get_client()
        response = client.chat(messages, max_tokens=512, temperature=0.2)
        return _parse_score_response(response)
    except Exception as e:
        log.error("LLM error scoring job '%s': %s", job.get("title", "?"), e)
        return {"score": 0, "keywords": "", "reasoning": f"LLM error: {e}"}


def score_jobs(jobs: pd.DataFrame, resume_text: str = "") -> pd.DataFrame:
    """Score jobs in place and add fit_* columns.

    Mutates the input DataFrame by creating/updating:
      - fit_score
      - fit_keywords
      - fit_reasoning
    """

    if jobs.empty:
        return jobs

    if not resume_text:
        try:
            with open(RESUME_MD, "r") as f:
                resume_text = f.read()
        except Exception as e:
            log.error("Error loading resume for batch scoring: %s", e)
            jobs["fit_reasoning"] = f"Error loading resume: {e}"
            return jobs

    for idx, job in jobs.iterrows():
        score_data = score_job(job.to_dict(), resume_text=resume_text)
        jobs.at[idx, "fit_score"] = score_data["score"]
        jobs.at[idx, "fit_keywords"] = score_data["keywords"]
        jobs.at[idx, "fit_reasoning"] = score_data["reasoning"]

    return jobs
