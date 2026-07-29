"""jobbot CLI - hunt, slopcheck, tailor, apply, status, run."""
import argparse
import datetime
from pathlib import Path

from jobbot import db

SLOP_GATE = 20  # slop_score above this blocks tailoring unless --force


def _kw(s):
    return [k.strip() for k in s.split(",") if k.strip()]


def _table(jobs):
    if not jobs:
        print("  (none)")
        return
    print(f"  {'score':>5} {'fit':>4}  {'status':<12} {'title':<40} {'company':<22} {'source':<9}")
    for j in jobs:
        fit = f"{j['fit']:.0f}" if (j.get("fit") or -1) >= 0 else "-"
        print(f"  {j['score']:>5.1f} {fit:>4}  {j['status']:<12.12} {(j['title'] or ''):<40.40} "
              f"{(j['company'] or ''):<22.22} {(j['source'] or ''):<9.9}")


def _load_resume(path):
    from jobbot import resume
    return resume.load_resume(path)


def cmd_hunt(args):
    from jobbot import sources, score
    resume_text = _load_resume(args.resume) if args.resume else ""
    kws = _kw(args.keywords or "")

    search_plan = None
    if resume_text:
        try:
            from jobbot import plan
            search_plan = plan.search_plan(resume_text)
            print(f"[plan] your resume suggests searching for: {', '.join(search_plan['titles'])}"
                  f" ({search_plan['seniority']} level)")
        except Exception as e:
            print(f"[plan] resume analysis unavailable ({e.__class__.__name__}) - using your keywords only")

    queries = list(dict.fromkeys(kws + (search_plan["titles"] if search_plan else [])))
    if search_plan and search_plan["seniority"] == "senior" and search_plan["titles"]:
        queries.append("senior " + search_plan["titles"][0])
    queries = queries[:6]
    if not queries:
        print("[hunt] give me keywords, a resume, or both - I have nothing to search with")
        return
    print(f"[hunt] searching each board for: {' | '.join(queries)}")

    # richer keyword set for scoring: what we searched + resume skills/expertise/certs/industries
    score_kws = queries
    if search_plan:
        score_kws = queries + search_plan["skills"] + search_plan["industries"] \
            + search_plan.get("expertise", []) + search_plan.get("certifications", [])
    jobs = sources.fetch(queries, args.area, results=args.results, country=args.country)
    for j in jobs:
        j["score"] = score.score_job(j, resume_text, score_kws)
    conn = db.connect()
    new = db.upsert(conn, jobs)
    # rescore everything still unprocessed so old rows reflect the current resume/keywords
    for j in db.list_jobs(conn, status="found"):
        db.update(conn, j["id"], score=score.score_job(j, resume_text, score_kws))
    print(f"[hunt] {len(jobs)} jobs found, {new} new. Top matches:")
    _table(db.list_jobs(conn, limit=15))


def cmd_slopcheck(args):
    from jobbot import slop
    text = _load_resume(args.resume)
    rep = slop.report(text, use_llm=args.llm)
    print(f"[slopcheck] score: {rep['score']}/100 (0 is clean, above {SLOP_GATE} fails the gate)")
    for f in rep["findings"]:
        loc = f"line {f['line']}" if f.get("line") else "doc"
        print(f"  [{f['severity']:<4}] {loc:<9} {f['term']}  ->  {f['tip']}")
    if rep.get("llm_notes"):
        print("\n[slopcheck] LLM reviewer notes:\n" + rep["llm_notes"])
    print("\n[slopcheck] verdict: " + ("CLEAN" if rep["score"] <= SLOP_GATE else "FAILS - fix the flagged items"))
    return rep["score"]


def _slop_gate(resume_text, force):
    from jobbot import slop
    sc = slop.slop_score(resume_text)
    if sc > SLOP_GATE and not force:
        print(f"[gate] Resume slop score {sc}/100 exceeds {SLOP_GATE}. "
              "Run 'slopcheck' to see the findings, fix them, or pass --force.")
        return False
    return True


def cmd_analyze(args):
    """Read the resume, derive the search plan + profile, print both for review."""
    from jobbot import plan, tailor
    resume_text = _load_resume(args.resume)
    try:
        p = plan.search_plan(resume_text)
        prof = tailor.ensure_profile(resume_text)
    except Exception as e:
        print(f"[analyze] FAILED: {e}")
        return
    print(f"[analyze] contact: {prof.get('name')} | {prof.get('email')} | {prof.get('phone')}")
    print(f"[analyze] will search for: {', '.join(p['titles'])} ({p['seniority']} level)")
    print(f"[analyze] skills: {', '.join(p['skills'])}")
    print(f"[analyze] industries: {', '.join(p['industries'])}")
    print("[analyze] done - review and correct it on the dashboard, then Run")


def cmd_match(args):
    from jobbot import match
    resume_text = _load_resume(args.resume)
    conn = db.connect()
    jobs = [j for j in db.list_jobs(conn, status="found")
            if (j.get("fit") or -1) < 0][:args.top]
    if not jobs:
        print("[match] no unscored jobs in 'found' state - run 'hunt' first")
        return
    for j in jobs:
        try:
            r = match.fit_score(j, resume_text)
        except Exception as e:
            print(f"[match] {j['title']} at {j['company']}: fit scoring failed: {e}")
            continue
        notes = r["reason"] + (f" Gaps: {r['gaps']}" if r["gaps"] else "")
        db.update(conn, j["id"], fit=r["score"], fit_notes=notes)
        print(f"[match] {r['score']:>3}/100  {j['title']} at {j['company']}")
        print(f"[match]          {notes}")


def cmd_tailor(args):
    from jobbot import tailor
    resume_text = _load_resume(args.resume)
    if not _slop_gate(resume_text, args.force):
        return
    profile = tailor.ensure_profile(resume_text)
    conn = db.connect()
    jobs = db.list_jobs(conn, status="found", min_score=args.min_score)
    low_fit = [j for j in jobs if 0 <= (j.get("fit") or -1) < args.min_fit]
    if low_fit:
        print(f"[tailor] skipping {len(low_fit)} jobs with fit below {args.min_fit}")
    jobs = [j for j in jobs if (j.get("fit") or -1) < 0 or j["fit"] >= args.min_fit]
    # prefer LLM fit when 'match' has run; fall back to keyword score
    jobs.sort(key=lambda j: j["fit"] if (j.get("fit") or -1) >= 0 else j["score"], reverse=True)
    jobs = jobs[:args.top]
    if not jobs:
        print("[tailor] no jobs in 'found' state above min score - run 'hunt' first")
        return
    for j in jobs:
        fit = f", fit {j['fit']:.0f}" if (j.get("fit") or -1) >= 0 else ""
        print(f"[tailor] {j['title']} at {j['company']} (score {j['score']}{fit})")
        brief = ""
        if not args.no_research:
            from jobbot import research
            brief = research.company_brief(j["company"])
            if brief:
                print(f"[research] found company info: {brief.splitlines()[0]}")
        paths = tailor.tailor_job(j, resume_text, profile, research=brief)
        db.update(conn, j["id"], status="tailored", tailor_dir=paths["dir"])
        print(f"[tailor]   -> {paths['dir']} (posting-overlap {paths['overlap']:.0%}, target under 10%)")


def cmd_apply(args):
    from jobbot import apply_bot, tailor
    resume_text = _load_resume(args.resume)
    profile = tailor.ensure_profile(resume_text)
    conn = db.connect()
    if args.id:
        jobs = [j for j in db.list_jobs(conn) if j["id"].startswith(args.id)]
    else:
        # pick up fresh tailored jobs AND ready ones from earlier dry runs,
        # best fit first - otherwise dry-run jobs would be stranded forever
        jobs = db.list_jobs(conn, status="tailored") + db.list_jobs(conn, status="ready")
        jobs.sort(key=lambda j: j["fit"] if (j.get("fit") or -1) >= 0 else j["score"],
                  reverse=True)
        jobs = jobs[:args.limit]
    if not jobs:
        print("[apply] nothing to apply to - run 'tailor' first (or pass --id)")
        return
    for j in jobs:
        cover = ""
        cl = Path(j.get("tailor_dir") or "") / "cover_letter.md"
        if j.get("tailor_dir") and cl.exists():
            cover = cl.read_text(encoding="utf-8")
        status, note = apply_bot.apply_to(
            j, profile, cover_letter_text=cover, resume_file=args.resume,
            auto=args.auto, headful=args.headful)
        fields = {"status": status, "notes": note}
        if status == "applied":
            fields["applied_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        db.update(conn, j["id"], **fields)
        print(f"[apply] {status.upper():<12} {j['title']} at {j['company']}")
        print(f"[apply]   {note}")


def cmd_status(args):
    conn = db.connect()
    jobs = db.list_jobs(conn)
    counts = {}
    for j in jobs:
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    print("[status] " + (", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "database empty"))
    _table(jobs[:12])
    flagged = [j for j in jobs if j["status"] == "needs_human"]
    if flagged:
        print("\n[status] needs your attention:")
        for j in flagged:
            print(f"  {j['id'][:8]}  {j['title']} at {j['company']}\n    {j['url']}\n    {j['notes']}")


def cmd_run(args):
    resume_text = _load_resume(args.resume)
    if not _slop_gate(resume_text, args.force):
        return  # fail the resume check BEFORE paying for a full scrape
    cmd_hunt(args)
    tailor_top = args.top
    args.top = max(tailor_top * 2, 10)  # fit-score a wider pool than we tailor
    cmd_match(args)
    args.top = tailor_top
    cmd_tailor(args)
    cmd_apply(args)
    cmd_status(args)


def main():
    p = argparse.ArgumentParser(prog="jobbot", description="Local job-application pipeline: hunt -> slopcheck -> tailor -> apply.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common_hunt(sp):
        sp.add_argument("--keywords", default="", help="comma-separated, e.g. 'data engineer,python'. "
                        "Optional when --resume is given - the AI derives searches from the resume.")
        sp.add_argument("--area", required=True, help="location, e.g. 'Toronto, ON' or 'Remote'")
        sp.add_argument("--results", type=int, default=25)
        sp.add_argument("--country", default="usa", help="country for Indeed (usa, canada, uk...)")

    sp = sub.add_parser("hunt", help="scrape boards, score against your resume, store")
    common_hunt(sp)
    sp.add_argument("--resume", help="resume file (pdf/docx/md/txt) for match scoring")
    sp.set_defaults(fn=cmd_hunt)

    sp = sub.add_parser("slopcheck", help="check resume for AI slop and cliches")
    sp.add_argument("--resume", required=True)
    sp.add_argument("--llm", action="store_true", help="add an LLM reviewer pass")
    sp.set_defaults(fn=cmd_slopcheck)

    sp = sub.add_parser("analyze", help="read the resume: derive searches, skills, contact info for review")
    sp.add_argument("--resume", required=True)
    sp.set_defaults(fn=cmd_analyze)

    sp = sub.add_parser("match", help="LLM fit score (0-100) for top unscored jobs")
    sp.add_argument("--resume", required=True)
    sp.add_argument("--top", type=int, default=10, help="how many jobs to score")
    sp.set_defaults(fn=cmd_match)

    sp = sub.add_parser("tailor", help="generate tailored resume + cover letter for top jobs")
    sp.add_argument("--resume", required=True)
    sp.add_argument("--top", type=int, default=5)
    sp.add_argument("--min-score", type=float, default=0, dest="min_score")
    sp.add_argument("--min-fit", type=float, default=35, dest="min_fit",
                    help="skip jobs whose LLM fit is below this (only when 'match' has run)")
    sp.add_argument("--no-research", action="store_true", dest="no_research",
                    help="skip fetching company websites for cover-letter context")
    sp.add_argument("--force", action="store_true", help="skip the slop gate")
    sp.set_defaults(fn=cmd_tailor)

    sp = sub.add_parser("apply", help="fill ATS application forms (dry run unless --auto)")
    sp.add_argument("--resume", required=True, help="resume FILE uploaded to forms")
    sp.add_argument("--id", help="apply to one specific job id (prefix ok)")
    sp.add_argument("--limit", type=int, default=3)
    sp.add_argument("--auto", action="store_true", help="actually submit when safe")
    sp.add_argument("--headful", action="store_true", help="visible browser; without --auto, pauses so YOU submit")
    sp.set_defaults(fn=cmd_apply)

    sp = sub.add_parser("status", help="pipeline overview")
    sp.set_defaults(fn=cmd_status)

    sp = sub.add_parser("web", help="local dashboard (applications, pipeline, needs-human)")
    sp.add_argument("--port", type=int, default=8737)
    sp.add_argument("--no-browser", action="store_true")
    sp.set_defaults(fn=lambda a: __import__("jobbot.web", fromlist=["web"]).serve(
        port=a.port, open_browser=not a.no_browser))

    sp = sub.add_parser("run", help="full pipeline: hunt -> gate -> tailor -> apply (dry) -> status")
    common_hunt(sp)
    sp.add_argument("--resume", required=True)
    sp.add_argument("--top", type=int, default=5)
    sp.add_argument("--min-score", type=float, default=0, dest="min_score")
    sp.add_argument("--min-fit", type=float, default=35, dest="min_fit")
    sp.add_argument("--limit", type=int, default=3)
    sp.add_argument("--auto", action="store_true")
    sp.add_argument("--headful", action="store_true")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--no-research", action="store_true", dest="no_research")
    sp.set_defaults(fn=cmd_run, id=None)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
