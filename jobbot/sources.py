"""Job discovery from multiple boards: python-jobspy (Indeed/LinkedIn/Google) + RemoteOK.

Public API:
  fetch(keywords, area, results=50, country="usa") -> list[dict]

Job dict keys: id, title, company, location, url, description, source, posted, score, status.
"""
import hashlib
import re

import requests
from jobspy import scrape_jobs

MAX_DESC_LEN = 15000


def s(v):
    """Coerce a possibly-NaN/None pandas cell to a str."""
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return str(v)


def _from_jobspy(queries, area, results, country):
    """Each query is searched separately - joining them into one string makes
    the boards fuzzy-match nonsense."""
    jobs = []
    per_q = max(5, results // max(1, len(queries)))
    for site in ["indeed", "linkedin", "google"]:
        for query in queries:
            try:
                jobs += _one_search(site, query, area, per_q, country)
            except Exception as e:
                print(f"[sources] {site} '{query}' failed: {e}")
    return jobs


def _one_search(site, query, area, results, country):
    kwargs = dict(
        site_name=[site],
        search_term=query,
        location=area,
        results_wanted=results,
        hours_old=168,
        country_indeed=country,
        description_format="markdown",
        verbose=0,
    )
    if site == "google":
        kwargs["google_search_term"] = f"{query} jobs near {area}"
    if site == "linkedin":
        kwargs["linkedin_fetch_description"] = True  # slower, but scoring/tailoring need it
    df = scrape_jobs(**kwargs)
    jobs = []
    for row in df.to_dict("records"):
        # prefer the "apply on company website" link when the board exposes
        # one - it goes straight to the employer's own form, which is where
        # the apply bot (and the human) actually applies
        url = s(row.get("job_url_direct")) or s(row.get("job_url"))
        title = s(row.get("title"))
        if not url or not title:
            continue
        jobs.append({
            "title": title,
            "company": s(row.get("company")),
            "url": url,
            "description": s(row.get("description")),
            "source": s(row.get("site")) or site,
            "posted": s(row.get("date_posted")),
            "location": s(row.get("location")) or area,
        })
    print(f"[sources] {site} '{query}': {len(jobs)} jobs")
    return jobs


def _from_remoteok(keywords):
    kw_lower = [k.lower() for k in keywords]
    jobs = []
    try:
        resp = requests.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "Mozilla/5.0 (jobbot)"},
            timeout=20,
        )
        data = resp.json()
        for entry in data:
            if "position" not in entry:
                continue
            tags = " ".join(entry.get("tags") or [])
            haystack = (
                s(entry.get("position")) + " " + s(entry.get("description")) + " " + tags
            ).lower()
            if not any(all(w in haystack for w in k.split()) for k in kw_lower):
                continue
            desc = re.sub(r"<[^>]+>", " ", s(entry.get("description")))
            jobs.append({
                "title": s(entry.get("position")),
                "company": s(entry.get("company")),
                "location": entry.get("location") or "Remote",
                "url": s(entry.get("url")),
                "description": desc,
                "source": "remoteok",
                "posted": s(entry.get("date")),
            })
        print(f"[sources] remoteok: {len(jobs)} jobs")
    except Exception as e:
        print(f"[sources] remoteok failed: {e}")
    return jobs


def fetch(queries, area, results=25, country="usa"):
    """queries: list of search strings, each searched separately on every board."""
    jobs = _from_jobspy(queries, area, results, country) + _from_remoteok(queries)

    seen = set()
    deduped = []
    for j in jobs:
        # ponytail: location in the key means cross-board reposts with differently
        # spelled locations survive as duplicates - better than silently dropping a
        # genuinely distinct same-title opening in another city.
        j["id"] = hashlib.sha1(
            f"{j['company']}|{j['title']}|{j.get('location', '')}".lower().encode("utf-8")).hexdigest()
        j["score"] = 0.0
        j["status"] = "found"
        j["description"] = j["description"][:MAX_DESC_LEN]
        if j["id"] in seen:
            continue
        seen.add(j["id"])
        deduped.append(j)

    print(f"[sources] total after dedupe: {len(deduped)}")
    return deduped
