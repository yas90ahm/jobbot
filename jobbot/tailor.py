"""Per-job application tailoring: profile setup, resume, and cover letter generation."""

import json
import os
import re

import yaml

from jobbot import llm
from jobbot import slop

PROFILE_DEFAULTS = {
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "github": "",
    "website": "",
    "skills": [],
    "years_experience": "",
    "work_authorization": "",
    "notice_period": "",
    "salary_expectation": "",
    "extra_notes": "",
}

BANNED = [
    "spearheaded", "leveraged", "synergy", "results-driven", "detail-oriented",
    "passionate about", "delve", "honed", "tapestry", "testament", "seamlessly",
    "cutting-edge", "utilize", "esteemed", "I am writing to express",
    "aligns perfectly", "hit the ground running", "wealth of experience",
    "excited to apply", "deep dive", "transformative", "meticulous", "dynamic",
    "proven track record", "game-changer", "revolutionize",
]
BANNED_TEXT = ", ".join(BANNED)

# Distilled from blader/humanizer, petergyang/no-ai-slop,
# Sahme115/ai-resume-humanizer-prompts, zhiweio/resume-as-code.
STYLE_RULES = """
WRITING RULES (all mandatory):
- Concrete nouns over abstract verbs. Name the actual project, system, tech, and
  number from the resume: "split the checkout monolith into three services" beats
  "built scalable microservices". Never write "cutting-edge tech" where you could
  name the tech.
- Every claim must survive the interview question "what specifically did you do?"
  If there is no concrete artifact behind a sentence, cut the sentence.
- Never inflate scope: "helped on" stays "helped on". Never invent metrics,
  names, dates, tech, or citations. Numbers only if the resume states them.
- Vary the rhythm: bullets must not all start with the same shape or all end
  with a generic impact clause. Natural item counts - no rule-of-three lists
  added for rhythm ("innovation, inspiration, and insight").
- Banned constructions: negative parallelism ("not just X, it's Y", "It's not
  X. It's Y."), false ranges ("from X to Y"), staccato fragments ("No fluff.
  No filler."), colon reveals ("The best part: ..."), aphorisms, throat-clearing
  openers ("Here's the thing"), hedging stacks ("could potentially").
- Banned words: "serves as", "showcases", "boasts", "landscape", "pivotal",
  "testament", "additionally" as a sentence opener; "in order to" -> "to";
  "due to the fact that" -> "because".
- No importance puffery, no weasel attribution ("experts agree"), no
  promotional adjectives. Neutral claims a skeptic would accept.
- Active voice. Lead with the point. Short sentences over tangled ones.
- Output at most 10 percent longer than the source material. Plain formatting:
  no em-dashes, no emoji, no bold-stuffing.
"""


def _apply_overrides(profile: dict, path: str = "data/profile_overrides.json") -> dict:
    """Merge non-empty answers from the web form (work authorization etc.)."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        profile.update({k: v for k, v in overrides.items() if v})
    return profile


def ensure_profile(resume_text: str, path: str = "profile.yaml") -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return _apply_overrides(yaml.safe_load(f))

    extracted = llm.ask_json(
        "Extract these fields from the resume text below and return as JSON: "
        "name, email, phone, location, linkedin, github, website, "
        "skills (list of strings), years_experience (string). "
        "Use an empty string (or empty list for skills) for anything not found.\n\n"
        + resume_text
    )
    profile = dict(PROFILE_DEFAULTS)
    profile.update(extracted)
    profile = _apply_overrides(profile)

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(profile, f, allow_unicode=True, sort_keys=False)

    print("[tailor] Wrote profile.yaml - review it and fill in blanks (work authorization etc).")
    return profile


def _slop_gate(text: str, prompt: str) -> str:
    rep = slop.report(text)
    sc = rep["score"]
    if sc > 20:
        terms = ", ".join(f["term"] for f in rep["findings"])
        retry_prompt = (
            prompt
            + f"\n\nYour previous draft tripped a cliche detector (score {sc}). "
            f"Flagged terms: {terms}. Rewrite avoiding all of them."
        )
        text = llm.ask(retry_prompt)
    return text


def _posting_overlap(text: str, desc: str) -> float:
    """Fraction of the text's 4-word phrases that appear verbatim in the posting.
    High overlap means the tailored resume is parroting the job ad."""
    def shingles(s):
        words = re.findall(r"[a-z0-9+#.]+", s.lower())
        return {" ".join(words[i:i + 4]) for i in range(len(words) - 3)}
    t, d = shingles(text), shingles(desc)
    if not t:
        return 0.0
    return len(t & d) / len(t)


def tailor_job(job: dict, resume_text: str, profile: dict, out_root: str = "data/tailored",
               research: str = "") -> dict:
    context = (
        f"Job title: {job.get('title', '')}\n"
        f"Company: {job.get('company', '')}\n"
        f"Location: {job.get('location', '')}\n\n"
        f"Job description:\n{(job.get('description') or '')[:6000]}\n\n"
        f"Full resume:\n{resume_text}"
    )

    resume_prompt = (
        context
        + "\n\nRewrite this resume in markdown, tailored to the job. Use ONLY facts "
        "present in the original resume - NEVER invent employers, titles, dates, "
        "numbers, or skills. Reorder and reword to emphasize what matches the job "
        "description. Keep the same sections and roughly the same length. Plain, "
        "direct, human wording. Banned words/phrases: " + BANNED_TEXT + ".\n"
        + STYLE_RULES +
        "\nOutput ONLY the markdown resume, no preamble."
    )
    resume_md = llm.ask(resume_prompt)
    resume_md = _slop_gate(resume_md, resume_prompt)

    # over-tailoring guard: a resume that echoes the posting verbatim reads as gamed
    desc = job.get("description") or ""
    overlap = _posting_overlap(resume_md, desc)
    if overlap > 0.10:
        resume_md = llm.ask(
            resume_prompt
            + f"\n\nYour previous draft copied too much wording verbatim from the job posting "
            f"({overlap:.0%} of its phrasing). Emphasize the same relevant experience but in "
            "the candidate's own words - do not echo the posting's sentences."
        )
        overlap = _posting_overlap(resume_md, desc)

    candidate_notes = "\n".join(
        f"{label}: {profile.get(key)}"
        for label, key in (("Work authorization", "work_authorization"),
                           ("Notice period", "notice_period"),
                           ("Notes from candidate", "extra_notes"))
        if profile.get(key))
    if candidate_notes:
        candidate_notes = f"\n\nCandidate details (use only if relevant):\n{candidate_notes}"

    research_block = ""
    if research:
        research_block = (
            f"\n\nVerified company research (fetched from their website):\n{research}\n"
            "You may use at most ONE specific fact from this research if it makes the "
            "letter stronger. Do not use any other knowledge about the company.")

    cover_prompt = (
        context
        + candidate_notes
        + research_block
        + "\n\nWrite a cover letter, max 220 words, plain text paragraphs. Direct and "
        "specific: reference the company and something concrete from the job "
        "description. Sound like a competent person writing an email, not a template. "
        "No greeting cliches. Banned: " + BANNED_TEXT + ".\n"
        + STYLE_RULES +
        "\nOutput ONLY the letter body, no preamble, no signature block."
    )
    cover_letter = llm.ask(cover_prompt)
    cover_letter = _slop_gate(cover_letter, cover_prompt)

    slug = re.sub(r"[^a-z0-9]+", "-", job["company"].lower()).strip("-")[:30]
    job_dir = os.path.join(out_root, f"{job['id'][:8]}-{slug}")
    os.makedirs(job_dir, exist_ok=True)

    resume_path = os.path.join(job_dir, "resume.md")
    cover_path = os.path.join(job_dir, "cover_letter.md")
    job_path = os.path.join(job_dir, "job.md")

    with open(resume_path, "w", encoding="utf-8") as f:
        f.write(resume_md)
    with open(cover_path, "w", encoding="utf-8") as f:
        f.write(cover_letter)
    with open(job_path, "w", encoding="utf-8") as f:
        f.write(
            f"# {job.get('title', '')}\n\n"
            f"**Company:** {job.get('company', '')}\n\n"
            f"**URL:** {job.get('url', '')}\n\n"
            f"## Description\n\n{job.get('description', '')}\n"
        )

    return {"dir": job_dir, "resume_md": resume_path, "cover_letter": cover_path,
            "overlap": round(overlap, 3)}
