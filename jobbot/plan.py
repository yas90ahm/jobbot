"""Resume-driven search plan: the AI reads the resume and decides what to search.

One LLM call, cached by resume hash in data/search_plan.json - regenerated only
when the resume changes.
"""
import hashlib
import json
from pathlib import Path

from jobbot import llm

CACHE = Path("data/search_plan.json")


def search_plan(resume_text):
    """Returns {"titles": [...], "seniority": str, "skills": [...], "industries": [...]}."""
    key = hashlib.sha1(resume_text.encode("utf-8")).hexdigest()[:12]
    if CACHE.exists():
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        if cached.get("key") == key:
            return cached
    out = llm.ask_json(
        "Read this resume and return JSON describing what to search on job boards "
        "for this person:\n"
        '{"titles": [4 to 6 job titles they should search for, most likely first, '
        "each 2-4 words exactly as employers post them], "
        '"seniority": "junior" or "mid" or "senior", '
        '"skills": [8 to 12 core skills from the resume], '
        '"industries": [up to 3 industries their experience fits]}\n'
        "Return ONLY the JSON.\n\n" + resume_text)
    plan = {
        "key": key,
        "titles": [str(t) for t in out.get("titles", []) if t][:6],
        "seniority": str(out.get("seniority", "mid")).lower(),
        "skills": [str(s) for s in out.get("skills", []) if s][:12],
        "industries": [str(i) for i in out.get("industries", []) if i][:3],
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return plan
