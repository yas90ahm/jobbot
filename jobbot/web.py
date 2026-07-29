"""Local dashboard + control panel: upload a resume, answer the general questions,
hit Run, and watch the pipeline. Stdlib http.server only, bound to 127.0.0.1.

The pipeline runs as a `python -m jobbot run ...` subprocess writing to
data/run.log, so the server stays responsive and the CLI stays the single
source of truth for behavior.
"""
import html
import json
import re
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer

from urllib.parse import parse_qs, urlparse

from jobbot import db, llm

STATUSES = [("applied", "applied"), ("ready", "ready to submit"),
            ("tailored", "tailored"), ("found", "found"),
            ("needs_human", "needs human"), ("skipped", "skipped")]

SETTINGS = Path("data/settings.json")
OVERRIDES = Path("data/profile_overrides.json")
RUNLOG = Path("data/run.log")
UPLOADS = Path("data/uploads")

RUN = {"proc": None}
LLM_TEST = {"ok": None, "msg": ""}

PROVIDERS = [
    ("claude-cli", "Claude Code CLI (default - free, uses your Claude login)"),
    ("ollama", "Ollama - local model on this computer (free, private)"),
    ("openai", "OpenAI API (needs API key)"),
    ("anthropic", "Anthropic API (needs API key)"),
    ("custom", "Custom OpenAI-compatible server (LM Studio, OpenRouter, Groq...)"),
]

CSS = """
:root { --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e;
  --muted:#898781; --grid:#e1e0d9; --border:rgba(11,11,11,.10);
  --good:#0ca30c; --goodtext:#006300; --warn:#fab219; }
@media (prefers-color-scheme: dark) {
  :root { --plane:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7;
    --grid:#2c2c2a; --border:rgba(255,255,255,.10); --goodtext:#0ca30c; }
}
* { box-sizing: border-box; margin: 0; }
body { background: var(--plane); color: var(--ink); padding: 24px;
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
h1 { font-size: 18px; font-weight: 600; margin-bottom: 4px; }
.sub { color: var(--muted); margin-bottom: 20px; font-size: 12px; }
.tiles { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }
.tile { background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 14px 18px; min-width: 130px; }
.tile .n { font-size: 34px; font-weight: 650; letter-spacing: -.5px;
  font-variant-numeric: tabular-nums; }
.tile .l { color: var(--ink2); font-size: 12px; display: flex;
  align-items: center; gap: 6px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 16px 18px; margin-bottom: 16px; overflow-x: auto; }
.card h2 { font-size: 13px; font-weight: 600; color: var(--ink2); margin-bottom: 10px; }
table { border-collapse: collapse; width: 100%; }
th { text-align: left; color: var(--muted); font-weight: 500; font-size: 12px;
  padding: 4px 12px 6px 0; border-bottom: 1px solid var(--grid); }
td { padding: 6px 12px 6px 0; border-bottom: 1px solid var(--grid);
  font-variant-numeric: tabular-nums; vertical-align: top; }
tr:last-child td { border-bottom: none; }
td.num, th.num { text-align: right; }
a { color: inherit; }
.chip { display: inline-flex; align-items: center; gap: 6px; color: var(--ink2);
  font-size: 12px; white-space: nowrap; }
.note { color: var(--muted); font-size: 12px; }
.empty { color: var(--muted); padding: 8px 0; }
form .row { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 3px; }
input[type=text], input[type=number], textarea, select { background: var(--plane);
  color: var(--ink); border: 1px solid var(--grid); border-radius: 6px;
  padding: 7px 9px; font: inherit; width: 100%; }
.f-wide { flex: 2 1 260px; } .f-med { flex: 1 1 150px; } .f-sm { flex: 0 1 110px; }
textarea { min-height: 54px; }
.btn { background: var(--ink); color: var(--plane); border: 0; border-radius: 6px;
  padding: 9px 22px; font: inherit; font-weight: 600; cursor: pointer; }
.btn-stop { background: transparent; color: var(--ink); border: 1px solid var(--grid); }
.btn-mini { background: transparent; color: var(--ink2); border: 1px solid var(--grid);
  border-radius: 5px; padding: 3px 10px; font: inherit; font-size: 12px; cursor: pointer; }
.btn-mini:hover { border-color: var(--ink2); }
details summary { cursor: pointer; color: var(--ink2); font-size: 13px; margin-bottom: 10px; }
.radio { display: inline-flex; gap: 6px; align-items: center; color: var(--ink2);
  font-size: 13px; margin-right: 16px; }
.radio input, .radio-line input[type=checkbox] { width: auto; }
pre.log { font: 12px/1.5 ui-monospace, Consolas, monospace; color: var(--ink2);
  max-height: 260px; overflow: auto; white-space: pre-wrap; }
.running { color: var(--goodtext); font-weight: 600; font-size: 13px; }
"""


def _esc(v):
    return html.escape(str(v or ""), quote=True)


def _chip(status):
    color = {"applied": "var(--good)", "needs_human": "var(--warn)"}.get(status, "var(--grid)")
    return (f'<span class="chip"><span class="dot" style="background:{color}"></span>'
            f'{_esc(dict(STATUSES).get(status, status))}</span>')


def _links(j):
    out = []
    if j.get("tailor_dir"):
        d = j["tailor_dir"].replace("\\", "/")
        out.append(f'<a href="/file?p={_esc(d)}/cover_letter.md" target="_blank">letter</a>')
        out.append(f'<a href="/file?p={_esc(d)}/resume.md" target="_blank">resume</a>')
    shot = Path("data/screenshots") / f"{j['id'][:8]}.png"
    if shot.exists():
        out.append(f'<a href="/file?p={_esc(shot.as_posix())}" target="_blank">screenshot</a>')
    return " &middot; ".join(out)


def _job_row(j):
    fit = f"{j['fit']:.0f}" if (j.get("fit") or -1) >= 0 else "-"
    title = _esc(j["title"])
    if j.get("url"):
        title = f'<a href="{_esc(j["url"])}" target="_blank">{title}</a>'
    return (f"<tr><td class=num>{j['score']:.0f}</td><td class=num>{fit}</td>"
            f"<td>{_chip(j['status'])}</td><td>{title}</td>"
            f"<td>{_esc(j['company'])}</td><td>{_esc(j['source'])}</td>"
            f"<td>{_links(j)}</td></tr>")


def _settings():
    if SETTINGS.exists():
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    return {}


def _running():
    return RUN["proc"] is not None and RUN["proc"].poll() is None


def _run_card():
    s = _settings()
    if _running():
        return f"""<div class="card"><h2>Pipeline</h2>
<p class="running">Running: {_esc(s.get('keywords'))} in {_esc(s.get('area'))} ...</p>
<form method="post" action="/stop" style="margin-top:10px">
<button class="btn btn-stop" type="submit">Stop run</button></form></div>"""

    resume_note = (f"current: {_esc(Path(s['resume']).name)}"
                   if s.get("resume") and Path(s["resume"]).exists()
                   else "no resume uploaded yet")
    ov = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
    return f"""<div class="card"><h2>Run the pipeline</h2>
<form method="post" action="/run" enctype="multipart/form-data">
<div class="row">
  <div class="f-wide"><label>Keywords, comma-separated (optional - leave blank and the AI
    picks searches from your resume)</label>
    <input type="text" name="keywords" value="{_esc(s.get('keywords'))}" placeholder="data engineer, python"></div>
  <div class="f-med"><label>Area / location</label>
    <input type="text" name="area" required value="{_esc(s.get('area'))}" placeholder="Toronto, ON"></div>
  <div class="f-sm"><label>Country (for Indeed, e.g. usa, canada)</label>
    <input type="text" name="country" value="{_esc(s.get('country') or 'usa')}"></div>
  <div class="f-sm"><label>Jobs to scrape</label>
    <input type="number" name="results" min="5" max="200" value="{_esc(s.get('results') or 25)}"></div>
  <div class="f-sm"><label>Jobs to tailor</label>
    <input type="number" name="top" min="1" max="20" value="{_esc(s.get('top') or 5)}"></div>
</div>
<div class="row"><div class="f-wide"><label>Resume (pdf / docx / md / txt) - {resume_note}</label>
  <input type="file" name="resume" accept=".pdf,.docx,.md,.txt"></div></div>
<details><summary>Application details (optional - used on forms and cover letters)</summary>
<div class="row">
  <div class="f-med"><label>Work authorization</label>
    <input type="text" name="work_authorization" value="{_esc(ov.get('work_authorization'))}" placeholder="e.g. Canadian citizen"></div>
  <div class="f-med"><label>Notice period</label>
    <input type="text" name="notice_period" value="{_esc(ov.get('notice_period'))}" placeholder="e.g. 2 weeks"></div>
  <div class="f-med"><label>Salary expectation</label>
    <input type="text" name="salary_expectation" value="{_esc(ov.get('salary_expectation'))}" placeholder="optional"></div>
</div>
<div class="row"><div class="f-wide"><label>Anything else the cover letters should know</label>
  <textarea name="extra_notes" placeholder="e.g. open to relocation; strongest in data platform work">{_esc(ov.get('extra_notes'))}</textarea></div></div>
</details>
<div class="row" style="align-items:center">
  <span class="radio"><input type="radio" name="mode" value="dry" {'checked' if s.get('mode') != 'auto' else ''}> dry run (fill forms, submit nothing)</span>
  <span class="radio"><input type="radio" name="mode" value="auto" {'checked' if s.get('mode') == 'auto' else ''}> auto-submit (sends real applications, no review)</span>
  <span class="radio radio-line"><input type="checkbox" name="research" {'checked' if s.get('research') != 'off' else ''}> research each company online</span>
  <span class="radio radio-line"><input type="checkbox" name="force" {'checked' if s.get('force') else ''}> skip resume quality check (normally required)</span>
  <button class="btn" type="submit">Run</button>
</div>
</form></div>"""


def _ai_card():
    cfg = llm.get_config()
    provider = cfg.get("provider") or "claude-cli"
    options = "".join(
        f'<option value="{v}" {"selected" if v == provider else ""}>{_esc(label)}</option>'
        for v, label in PROVIDERS)
    test = ""
    if LLM_TEST["ok"] is not None:
        color = "var(--good)" if LLM_TEST["ok"] else "var(--warn)"
        word = "Working" if LLM_TEST["ok"] else "Failed"
        test = (f'<p class="chip" style="margin-bottom:10px">'
                f'<span class="dot" style="background:{color}"></span>'
                f'{word}: {_esc(LLM_TEST["msg"])}</p>')
    key_note = "(a key is saved - leave blank to keep it)" if cfg.get("api_key") else "(only for paid APIs)"
    return f"""<div class="card"><details {'open' if LLM_TEST["ok"] is False else ''}>
<summary><b>AI settings</b> - current: {_esc(dict(PROVIDERS).get(provider, provider))}</summary>
{test}
<p class="note" style="margin-bottom:10px">Pick <b>Claude Code</b> if you already use Claude on this
computer. <b>Ollama</b> runs a free, private model on your own machine (install it from ollama.com,
then run: ollama pull llama3.1). Otherwise pick <b>OpenAI</b> or <b>Anthropic</b> and paste an API
key from their website.</p>
<form method="post" action="/llm">
<div class="row">
  <div class="f-wide"><label>Who writes the tailoring - pick what you have</label>
    <select name="provider">{options}</select></div>
  <div class="f-med"><label>Model name (blank = default for Claude)</label>
    <input type="text" name="model" value="{_esc(cfg.get('model'))}" placeholder="llama3.1 / gpt-4o-mini"></div>
</div>
<div class="row">
  <div class="f-med"><label>API key {key_note}</label>
    <input type="password" name="api_key" placeholder="paste key or leave blank"></div>
  <div class="f-wide"><label>Server URL (only for Custom; Ollama is automatic)</label>
    <input type="text" name="base_url" value="{_esc(cfg.get('base_url'))}" placeholder="http://localhost:1234/v1"></div>
</div>
<button class="btn" type="submit">Save and test</button>
</form></details></div>"""


def _log_card():
    if not RUNLOG.exists():
        return ""
    lines = RUNLOG.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
    state = "running" if _running() else "last run"
    return (f'<div class="card"><h2>Pipeline log ({state})</h2>'
            f'<p class="note">If a run fails, the reason is usually in the last few lines - '
            f'copy them if you need to ask someone for help.</p>'
            f'<pre class="log">{_esc(chr(10).join(lines)) or "(no output yet)"}</pre></div>')


def render(db_path="data/jobs.db"):
    conn = db.connect(db_path)
    jobs = db.list_jobs(conn)
    conn.close()
    counts = {}
    for j in jobs:
        counts[j["status"]] = counts.get(j["status"], 0) + 1

    tiles = ""
    for status, label in STATUSES:
        n = counts.get(status, 0)
        if n == 0 and status in ("ready", "skipped"):
            continue
        tiles += (f'<div class="tile"><div class="n">{n}</div>'
                  f'<div class="l">{_chip(status)}</div></div>')

    applied = sorted([j for j in jobs if j["status"] == "applied"],
                     key=lambda j: j.get("applied_at") or "", reverse=True)
    applied_rows = "".join(
        f"<tr><td>{_esc((j.get('applied_at') or '')[:16].replace('T', ' '))}</td>"
        f"<td><a href=\"{_esc(j['url'])}\" target=\"_blank\">{_esc(j['title'])}</a></td>"
        f"<td>{_esc(j['company'])}</td><td class=note>{_esc(j.get('notes'))}</td></tr>"
        for j in applied) or '<tr><td colspan="4" class="empty">No applications submitted yet.</td></tr>'

    flagged = [j for j in jobs if j["status"] in ("needs_human", "ready")]
    flagged.sort(key=lambda j: j["fit"] if (j.get("fit") or -1) >= 0 else j["score"],
                 reverse=True)
    flagged_rows = "".join(
        f"<tr><td><a href=\"{_esc(j['url'])}\" target=\"_blank\">{_esc(j['title'])}</a>"
        f"<div class=note>{_esc(j['company'])}</div></td>"
        f"<td>{_chip(j['status'])}</td><td class=note>{_esc(j.get('notes'))}</td>"
        f"<td>{_links(j)}</td>"
        f'<td><form method="post" action="/mark" style="white-space:nowrap">'
        f'<input type="hidden" name="id" value="{_esc(j["id"])}">'
        f'<button class="btn-mini" name="set" value="applied">I applied</button> '
        f'<button class="btn-mini" name="set" value="skipped">Skip</button></form></td></tr>'
        for j in flagged)
    flagged_card = (f'<div class="card"><h2>Your to-do list ({len(flagged)} jobs need you)</h2>'
                    f'<p class="note">Best matches first. Open the job, use your tailored letter from '
                    f'"materials", finish the application, then mark it here so the list shrinks.</p>'
                    f'<table><tr><th>Job</th><th>status</th><th>Why it needs you</th>'
                    f'<th>materials</th><th>done?</th></tr>'
                    f'{flagged_rows}</table></div>') if flagged else ""

    top = sorted(jobs, key=lambda j: j["fit"] if (j.get("fit") or -1) >= 0 else j["score"],
                 reverse=True)[:30]
    job_rows = "".join(_job_row(j) for j in top) or \
        '<tr><td colspan="7" class="empty">Nothing yet - fill in the form above and hit Run.</td></tr>'

    refresh = 8 if _running() else 30
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="{refresh}"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>jobbot dashboard</title><style>{CSS}</style></head><body>
<h1>jobbot</h1><div class="sub">{len(jobs)} jobs tracked &middot; refreshes every {refresh}s</div>
{_run_card()}
{_ai_card()}
{_log_card()}
<div class="tiles">{tiles}</div>
{flagged_card}
<div class="card"><h2>Applications</h2>
<table><tr><th>When</th><th>Job</th><th>Company</th><th>Notes</th></tr>{applied_rows}</table></div>
<div class="card"><h2>Pipeline (top 30 by fit, then score)</h2>
<p class="note">score = quick keyword match &middot; fit = the AI's judgment of how well you
match the role (0-100, scored by a recruiter-style review of your resume vs the posting)</p>
<table><tr><th class=num>score</th><th class=num>fit</th><th>status</th>
<th>job</th><th>company</th><th>source</th><th>materials</th></tr>{job_rows}</table></div>
</body></html>"""


def _parse_multipart(content_type, body):
    m = re.search(r"boundary=([^;]+)", content_type or "")
    if not m:
        return {}, {}
    boundary = m.group(1).strip('"').encode("utf-8")
    fields, files = {}, {}
    for part in body.split(b"--" + boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        head, _, data = part.partition(b"\r\n\r\n")
        head_text = head.decode("utf-8", "replace")
        name = re.search(r'name="([^"]+)"', head_text)
        if not name:
            continue
        fname = re.search(r'filename="([^"]*)"', head_text)
        if fname and fname.group(1):
            files[name.group(1)] = (fname.group(1), data)
        else:
            fields[name.group(1)] = data.decode("utf-8", "replace").strip()
    return fields, files


def _start_run(fields, files):
    """Returns an error string, or None on success."""
    settings = _settings()
    if "resume" in files:
        UPLOADS.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w.-]", "_", files["resume"][0]) or "resume"
        path = UPLOADS / safe
        path.write_bytes(files["resume"][1])
        settings["resume"] = str(path)
    if not settings.get("resume") or not Path(settings["resume"]).exists():
        return "No resume: upload one before running."

    for k in ("keywords", "area", "country", "results", "top", "mode"):
        if fields.get(k):
            settings[k] = fields[k]
    settings["force"] = bool(fields.get("force"))
    settings["research"] = "on" if fields.get("research") else "off"
    settings["keywords"] = fields.get("keywords", settings.get("keywords", ""))
    if not settings.get("area"):
        return "Area is required."
    if not settings.get("keywords") and not settings.get("resume"):
        return "Give me keywords, a resume, or both."
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(settings, indent=1), encoding="utf-8")

    OVERRIDES.write_text(json.dumps({
        k: fields.get(k, "") for k in
        ("work_authorization", "notice_period", "salary_expectation", "extra_notes")
    }, indent=1), encoding="utf-8")

    cmd = [sys.executable, "-u", "-m", "jobbot", "run",
           "--keywords", settings["keywords"], "--area", settings["area"],
           "--country", settings.get("country") or "usa",
           "--results", str(settings.get("results") or 25),
           "--top", str(settings.get("top") or 5),
           "--resume", settings["resume"]]
    if settings.get("mode") == "auto":
        cmd.append("--auto")
    if settings.get("force"):
        cmd.append("--force")
    if settings.get("research") == "off":
        cmd.append("--no-research")
    log = open(RUNLOG, "w", encoding="utf-8")
    RUN["proc"] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    return None


def serve(port=8737, db_path="data/jobs.db", open_browser=True):
    class Handler(BaseHTTPRequestHandler):
        def _page(self, status=200, body=None):
            data = (body or render(db_path)).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self):
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/file":
                p = parse_qs(parsed.query).get("p", [""])[0]
                full = Path(p).resolve()
                root = Path("data").resolve()
                if not (full.is_file() and full.is_relative_to(root)):
                    return self._page(404, "<p>Not found.</p><p><a href='/'>back</a></p>")
                ctype = ("image/png" if full.suffix == ".png"
                         else "text/plain; charset=utf-8")
                data = full.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self._page()

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.path == "/stop" and _running():
                RUN["proc"].terminate()
            elif self.path == "/mark":
                q = {k: v[0] for k, v in
                     parse_qs(body.decode("utf-8", "replace")).items()}
                if q.get("id") and q.get("set") in ("applied", "skipped"):
                    import datetime
                    conn = db.connect(db_path)
                    fields = {"status": q["set"], "notes": "marked by you on the dashboard"}
                    if q["set"] == "applied":
                        fields["applied_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                    db.update(conn, q["id"], **fields)
                    conn.close()
            elif self.path == "/llm":
                q = {k: v[0].strip() for k, v in
                     parse_qs(body.decode("utf-8", "replace")).items()}
                cfg = llm.get_config()
                cfg["provider"] = q.get("provider") or "claude-cli"
                cfg["model"] = q.get("model", "")
                cfg["base_url"] = q.get("base_url", "")
                if q.get("api_key"):
                    cfg["api_key"] = q["api_key"]
                llm.save_config(cfg)
                try:
                    reply = llm.ask("Reply with exactly the word OK and nothing else.",
                                    timeout=90)
                    LLM_TEST["ok"] = True
                    LLM_TEST["msg"] = f"the model replied ({reply[:40]})"
                except Exception as e:
                    LLM_TEST["ok"] = False
                    LLM_TEST["msg"] = str(e)[:200]
            elif self.path == "/run" and not _running():
                fields, files = _parse_multipart(self.headers.get("Content-Type"), body)
                err = _start_run(fields, files)
                if err:
                    return self._page(400, f"<p>{_esc(err)}</p><p><a href='/'>back</a></p>")
            self._redirect()

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"[web] dashboard at {url} (Ctrl+C to stop)")
    if open_browser:
        Timer(0.5, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        if _running():
            RUN["proc"].terminate()
        print("\n[web] stopped")
