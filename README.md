# jobbot

A job-application assistant that runs entirely on your own computer. Give it an
area and your resume (keywords optional - the AI derives what to search from the
resume itself: titles, seniority, skills). It finds jobs, scores how well each fits you,
checks your resume for AI-cliche writing, researches each company, writes a
tailored resume + cover letter per job, and fills out application forms for you.

**New here? Read [HOW_TO_USE.md](HOW_TO_USE.md) - it walks through everything
with no technical knowledge assumed.**

## Quick start (Windows)

1. Install Python from https://www.python.org/downloads - tick **"Add python.exe to PATH"**.
2. Double-click **`setup.bat`** (once).
3. Double-click **`start_jobbot.bat`** - the dashboard opens in your browser.

## Manual setup (any platform)

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python -m jobbot web        # dashboard
.venv\Scripts\python -m jobbot --help     # CLI stages: hunt/slopcheck/match/tailor/apply/status
```

AI runs through whichever you have: the Claude Code CLI (default, free with your
Claude login), a local model via Ollama, or any OpenAI-compatible / Anthropic API
key - pick and test it in the dashboard's **AI settings** panel.

## What it will and won't do

- Fills direct-employer application forms on 8 systems (Greenhouse, Lever,
  Ashby, Workable, JazzHR, Breezy, Recruitee, BambooHR). Job boards' "apply on
  company website" links are followed automatically to reach them. Dry-run by
  default; submits only in auto mode when every required field is filled and no
  CAPTCHA is present.
- Never automates LinkedIn/Indeed "Easy Apply" (against their terms), never
  bypasses CAPTCHAs, never touches demographic/EEO questions - those are always
  handed to you with a link and your tailored letter.
- Never invents resume facts: tailoring may only reorder and reword what your
  resume actually says, is re-checked by the cliche detector, and is capped at
  10% verbatim overlap with the job posting.
- Writing quality rules are distilled from
  [blader/humanizer](https://github.com/blader/humanizer),
  [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop),
  [Sahme115/ai-resume-humanizer-prompts](https://github.com/Sahme115/ai-resume-humanizer-prompts),
  and [zhiweio/resume-as-code](https://github.com/zhiweio/resume-as-code) -
  enforced two ways: as instructions the tailoring AI must follow, and as
  patterns the slop detector mechanically rejects afterward.

## Where things live

Everything personal stays in gitignored local files: `data/` (job database,
tailored letters, screenshots, settings, AI config) and `profile.yaml` (contact
info extracted from your resume - review it after the first run). Samples in
`samples/` are fictional; one is deliberately bad to demo the resume check.
