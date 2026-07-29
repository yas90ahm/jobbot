# How to use jobbot

No technical knowledge needed. Total setup time: about 10 minutes, once.

## 1. One-time setup

1. Install Python: go to https://www.python.org/downloads, download, run the
   installer, and **tick the box "Add python.exe to PATH"** before clicking Install.
2. Double-click **`setup.bat`** in the jobbot folder. A black window does its
   thing for a few minutes and says "Done!".

## 2. Start it

Double-click **`start_jobbot.bat`**. Your browser opens the dashboard.
Keep the black window open while you use jobbot; close it to stop.

## 3. Fill in the form and run

At the top of the dashboard:

- **Keywords** - optional. Leave blank and the AI reads your resume and decides
  what to search for (job titles, your seniority level). Or type your own,
  comma-separated (`data analyst, sql`) - each is searched separately, and the
  AI's resume-based searches are added on top.
- **Area** - where: `Toronto, ON` (or `Remote`)
- **Country** - where Indeed should search: `usa`, `canada`, `uk`...
- **Resume** - upload your resume (PDF, Word, or text)
- Open **"Application details"** and fill in work authorization etc. - this
  goes into your cover letters and application forms.
- Leave **dry run** selected for now. Click **Run**.

The first thing jobbot does is check your resume for cliche, robotic writing
("spearheaded", "leveraged cutting-edge...", too many long dashes). If it fails,
the log tells you exactly which lines to fix and why. Fix them and run again -
a resume that reads like a human wrote it gets more interviews, so don't skip this.

## 4. While it runs

The page refreshes itself. Watch the **Pipeline log**. A full run takes roughly
10-20 minutes depending on how many jobs it tailors. What it's doing:

1. Searching Indeed, LinkedIn, Google Jobs, and RemoteOK
2. Having the AI read each promising job against your resume and score the
   **fit** (0-100, like a blunt recruiter would)
3. Looking up each company's real website for facts to use in your letter
4. Writing a tailored resume and cover letter for the best-fitting jobs
5. Filling out application forms (without submitting - it's a dry run)

## 5. Read the results

- **Tiles at the top** - how many jobs are at each stage. "applied" is your total.
- **Needs your attention** - jobs it couldn't finish for you (LinkedIn-only
  postings, CAPTCHAs, custom questions). Each row has the job link and your
  tailored **letter** - open both, paste, answer the custom questions, submit.
  This is normal: expect many jobs here. The letter was the hard part, and it's done.
- **Pipeline table** - every job found, best matches first. Click **letter** /
  **resume** to read what it wrote; **screenshot** to see a filled form.

## 6. Actually applying

Three ways, from safest to most automatic:

- **Manual** (always available): open the job link, copy your tailored letter, apply yourself.
- **Assisted** (recommended): from a terminal in the jobbot folder run
  `.venv\Scripts\python -m jobbot apply --resume <your resume> --headful` - a
  browser opens and jobbot keeps auto-filling every page as you click through.
  This works on ANY site, including Workday/Taleo/iCIMS company portals: you
  create the account and click Submit, jobbot does the tedious typing on each
  screen. Add `--id <first characters of the job id>` to do one specific job.
- **Auto**: select "auto-submit" in the form and Run. jobbot submits only when
  every required field is filled and there's no CAPTCHA; anything uncertain goes
  to your to-do list instead. It never half-submits.

## A good daily routine

1. **Morning**: open the dashboard, hit **Run** (your settings are remembered).
   Close the laptop, go live your life - it takes 10-20 minutes on its own.
2. **Afternoon**: open the dashboard and work through **Your to-do list** - the
   jobs that need a human, best matches first. For each one: open the job link,
   use your tailored letter from "materials", finish the application, then click
   **I applied** (or **Skip** if it's not for you). The list shrinks as you go.
3. Applications you finish are counted in the "applied" tile, so you can watch
   the number grow over the week.

## 7. If the AI part complains

If a run fails with a message about Claude/AI, open **AI settings** on the
dashboard, pick what you have, and press **Save and test** until you see
"Working". Options, in order of ease:

- **Claude Code** - you already have it if you use Claude on this computer. Free.
- **Ollama** - free and private, runs on your machine. Install from ollama.com,
  then in a terminal: `ollama pull llama3.1`. Pick Ollama, type `llama3.1` as
  the model, save and test.
- **OpenAI / Anthropic API key** - paid; paste the key from their website.

## Quick answers

- **Run it again tomorrow?** Yes - jobs already seen are skipped; the form
  remembers your answers. Re-run whenever.
- **Something failed?** The reason is in the last lines of the Pipeline log.
- **Wrong info on forms?** Edit `profile.yaml` in the jobbot folder (it's plain
  text) - that's what forms get filled with.
- **Is my data private?** Everything - resume, letters, job list, AI keys -
  stays in the jobbot folder on your computer.
