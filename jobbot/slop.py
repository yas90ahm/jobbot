"""AI-slop / cliche detector for resumes and cover letters.

Public API: scan(text), slop_score(text), report(text, use_llm=False), is_clean(text, max_score=20)
"""

import re

# term -> plain-English replacement tip. 8 pts each in slop_score.
HIGH = {
    "spearheaded": "led / ran / started",
    "leveraged": "used",
    "leveraging": "using",
    "synergy": "working together",
    "results-driven": "cut it - show a result instead",
    "detail-oriented": "show it, don't claim it",
    "self-starter": "cut it",
    "go-getter": "cut it",
    "think outside the box": "cut it",
    "proven track record": "name the actual result",
    "passionate about": "say what you did, not how you feel",
    "delve": "dig into / look at",
    "delving": "digging into",
    "honed": "improved / sharpened",
    "tapestry": "cut it",
    "testament to": "shows",
    "fast-paced environment": "cut it",
    "game-changer": "cut it",
    "revolutionize": "improve",
    "seamlessly": "cut it or say how",
    "cutting-edge": "name the actual tech",
    "state-of-the-art": "name the actual tech",
    "utilize": "use",
    "utilized": "used",
    "utilizing": "using",
    "esteemed": "cut it",
    "i am writing to express": "just start with the point",
    "aligns perfectly": "cut it",
    "hit the ground running": "cut it",
    "wealth of experience": "say the years or the work",
    "excited to apply": "cut it - show specific interest instead",
    "deep dive": "close look",
    "transformative": "cut it",
    "meticulous": "careful - or show it",
    "meticulously": "carefully",
    "dynamic environment": "cut it",
    "elevate": "improve / raise",
    "here's the thing": "just say the thing",
    "let's dive in": "cut it",
    "what nobody tells you": "cut it",
    "leveraged synergistic": "used - and name what",
}

# term -> tip. 3 pts each in slop_score.
MED = {
    "robust": "solid / reliable",
    "holistic": "complete",
    "innovative": "say what was new",
    "team player": "show collaboration instead",
    "excellent communication skills": "show it with an example",
    "responsible for": "use an active verb: built, ran, led",
    "extensive experience": "say the years",
    "proven ability": "name the result",
    "strong background": "say the years or projects",
    "furthermore": "also - or cut",
    "moreover": "also - or cut",
    "in conclusion": "cut it",
    "various": "name them",
    "numerous": "give the number",
    "stakeholders": "name who",
    "serves as": "say what it actually does",
    "showcases": "show the result itself",
    "showcasing": "show the result itself",
    "boasts": "state it plainly",
    "landscape": "name the actual field",
    "pivotal": "say what changed",
    "studies show": "cite the actual study or cut it",
    "experts agree": "which experts? name them or cut it",
    "in order to": "to",
    "due to the fact that": "because",
    "a testament": "shows",
}


def _phrase_pattern(term):
    """Word-boundary regex for a term; multi-word terms match as phrases."""
    words = [re.escape(w) for w in term.split(" ")]
    return re.compile(r"\b" + r"\s+".join(words) + r"\b", re.IGNORECASE)


def _build_terms():
    terms = []
    for term, tip in HIGH.items():
        terms.append((term, "high", tip, _phrase_pattern(term)))
    for term, tip in MED.items():
        terms.append((term, "med", tip, _phrase_pattern(term)))
    return terms


_TERMS = _build_terms()

_NOT_ONLY_RE = re.compile(r"not only.{0,60}?but also", re.IGNORECASE | re.DOTALL)
_ELLIPSIS_RE = re.compile(r"…|\.{3,}")
# negative parallelism: "not just X, it's Y" / "It's not X. It's Y." / "Not a X. Not a Y."
_NEG_PARALLEL_RE = re.compile(
    r"not (?:just|only|merely|simply)\b[^.!?]{0,60}?\b(?:but|it'?s|it is)\b"
    r"|it'?s not [^.!?]{2,50}[.!?] ?it'?s\b"
    r"|\bnot an? [^.!?]{2,40}[.!?] ?not an? ", re.IGNORECASE)


def scan(text):
    """Return list of findings: {"line": int, "term": str, "severity": "high"|"med", "tip": str}."""
    findings = []
    for lineno, line in enumerate(text.split("\n"), start=1):
        for term, severity, tip, pattern in _TERMS:
            if pattern.search(line):
                findings.append({"line": lineno, "term": term, "severity": severity, "tip": tip})

    em_dash_count = text.count("—")
    if em_dash_count > 2:
        findings.append({
            "line": 0,
            "term": f"em-dash overuse ({em_dash_count} found)",
            "severity": "high",
            "tip": "replace with periods or commas - a classic AI tell",
        })

    if _NOT_ONLY_RE.search(text):
        findings.append({
            "line": 0,
            "term": "not only ... but also",
            "severity": "med",
            "tip": "restructure - AI-favorite construction",
        })

    if _NEG_PARALLEL_RE.search(text):
        findings.append({
            "line": 0,
            "term": "negative parallelism (not just X, it's Y)",
            "severity": "med",
            "tip": "state it directly - AI-favorite construction",
        })

    if any(ord(ch) >= 0x1F000 for ch in text):
        findings.append({"line": 0, "term": "emoji", "severity": "high", "tip": "no emoji in a resume"})

    if _ELLIPSIS_RE.search(text):
        findings.append({"line": 0, "term": "ellipsis", "severity": "med", "tip": "cut trailing ellipses"})

    return findings


def slop_score(text):
    """0..100 score, 0 = clean. high=8pts, med=3pts, plus em-dash overuse penalty."""
    findings = scan(text)
    score = sum(8 if f["severity"] == "high" else 3 for f in findings)

    em_dash_count = text.count("—")
    if em_dash_count > 2:
        score += 4 * (em_dash_count - 2)

    return min(100, score)


def report(text, use_llm=False):
    """{"score": int, "findings": list, "llm_notes": str}."""
    findings = scan(text)
    score = slop_score(text)
    llm_notes = ""

    if use_llm:
        try:
            from jobbot import llm
            prompt = (
                "Act as a blunt hiring manager reviewing this resume/cover letter text. "
                "Call out any AI-sounding or cliche phrasing and any vague, unverifiable "
                "claims. List at most 8 concrete rewrite suggestions in plain text.\n\n"
                f"TEXT:\n{text}"
            )
            llm_notes = llm.ask(prompt)
        except Exception as e:
            llm_notes = f"LLM review unavailable: {e}"

    return {"score": score, "findings": findings, "llm_notes": llm_notes}


def is_clean(text, max_score=20):
    return slop_score(text) <= max_score


def demo():
    clean = "Built a data pipeline that cut report time from 2 days to 4 hours."
    assert scan(clean) == []
    assert slop_score(clean) == 0
    assert is_clean(clean)

    slop = "I am writing to express my passionate, results-driven, detail-oriented synergy."
    findings = scan(slop)
    assert any(f["term"] == "results-driven" and f["severity"] == "high" for f in findings)
    assert any(f["term"] == "synergy" for f in findings)
    assert slop_score(slop) > 20
    assert not is_clean(slop)

    dashes = "a—b—c—d"  # 3 em-dashes, > 2
    dash_findings = scan(dashes)
    assert any(f["term"].startswith("em-dash overuse") for f in dash_findings)
    assert slop_score(dashes) == 8 + 4 * (3 - 2)

    both = "Not only did I code, but also I tested it."
    assert any(f["term"] == "not only ... but also" for f in scan(both))

    emoji_text = "great work \U0001F600"
    assert any(f["term"] == "emoji" for f in scan(emoji_text))

    ellipsis_text = "and then... more work"
    assert any(f["term"] == "ellipsis" for f in scan(ellipsis_text))

    rep = report(clean)
    assert rep["score"] == 0 and rep["findings"] == [] and rep["llm_notes"] == ""

    print("slop.py self-check OK")
