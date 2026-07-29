"""LLM-judged fit score between a resume and a job - deeper than keyword counting."""
from jobbot import llm


def fit_score(job, resume_text):
    """Returns {"score": int 0-100, "reason": str, "gaps": str}."""
    prompt = (
        f"Job title: {job.get('title', '')}\n"
        f"Company: {job.get('company', '')}\n"
        f"Job description:\n{(job.get('description') or '')[:6000]}\n\n"
        f"Candidate resume:\n{resume_text}\n\n"
        "You are a blunt, experienced recruiter. Judge how well this candidate fits "
        "this job. Weigh transferable skills, domain, and seniority honestly - do NOT "
        "require exact keyword matches, and do NOT reward buzzword overlap. A perfect "
        "100 means an unusually strong direct fit; 50 means worth a shot; below 35 "
        "means applying wastes everyone's time.\n"
        'Return JSON only: {"score": <0-100 int>, "reason": "<one sentence>", '
        '"gaps": "<the 1-3 biggest gaps, comma-separated, or empty string>"}'
    )
    out = llm.ask_json(prompt)
    return {
        "score": max(0, min(100, int(out.get("score", 0)))),
        "reason": str(out.get("reason", "")),
        "gaps": str(out.get("gaps", "")),
    }
