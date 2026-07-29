"""Company research: fetch real text from the company's website, summarize it
with the LLM, cache per company. Fail-soft everywhere - research that fails
never blocks tailoring, it just yields an empty brief.

The code does the fetching; the AI only reads fetched text. That keeps briefs
factual (no model memory of companies) and works with fully-local models.
"""
import re
from pathlib import Path

import requests

from jobbot import llm

CACHE = Path("data/research")
UA = {"User-Agent": "Mozilla/5.0 (compatible; jobbot-research)"}
SKIP_DOMAINS = ("linkedin.", "indeed.", "glassdoor.", "wikipedia.", "facebook.",
                "instagram.", "youtube.", "twitter.", "x.com/", "crunchbase.",
                "zoominfo.", "duckduckgo.", "reddit.", "bloomberg.")


def _strip_html(html_text):
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _find_site(company):
    # Clearbit's free autocomplete maps a company name to its official domain.
    try:
        r = requests.get("https://autocomplete.clearbit.com/v1/companies/suggest",
                         params={"query": company}, headers=UA, timeout=15)
        if r.ok and r.json():
            return "https://" + r.json()[0]["domain"]
    except Exception:
        pass
    # fallback: guess <companyname>.com and see if it answers
    slug = re.sub(r"[^a-z0-9]", "", company.lower())
    if slug:
        try:
            url = f"https://{slug}.com"
            # GET, not HEAD - many sites reject HEAD but serve GET fine
            r = requests.get(url, headers=UA, timeout=10, stream=True)
            r.close()
            if r.status_code < 400:
                return url
        except Exception:
            pass
    return ""


def company_brief(company):
    """Returns a short factual brief ('Source: <url>' + bullets), or ''. Cached."""
    if not company:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")[:40]
    cached = CACHE / f"{slug}.md"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    try:
        site = _find_site(company)
        if not site:
            return ""
        page = requests.get(site, headers=UA, timeout=20)
        text = _strip_html(page.text)[:5000]
        if len(text) < 200:
            return ""
        brief = llm.ask(
            f"Company: {company}\nTheir website ({site}) says:\n{text}\n\n"
            "Write 3 short factual bullet points about what this company actually "
            "does, for someone writing a cover letter to them. Use ONLY facts "
            "stated in the text above - no outside knowledge, no hype words. "
            "If the text is clearly not about this company, reply with exactly: SKIP")
        if not brief or brief.strip().upper() == "SKIP" or len(brief) < 30:
            return ""
        brief = f"Source: {site}\n{brief.strip()}"
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(brief, encoding="utf-8")
        return brief
    except Exception as e:
        print(f"[research] {company}: skipped ({e.__class__.__name__})")
        return ""
