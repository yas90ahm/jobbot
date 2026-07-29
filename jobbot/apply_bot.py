"""Playwright form-filler for direct-employer ATS pages (Greenhouse, Lever, Ashby, Workable).

Fills contact fields, uploads the resume, pastes the cover letter, screenshots the
result. Auto-submits only when every required field is filled and no visible CAPTCHA
is present; anything it cannot safely finish comes back as needs_human. It never
bypasses CAPTCHAs or bot checks - those are always handed to the human.
"""
import re
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

ATS_HOSTS = {
    "greenhouse": ("greenhouse.io",),
    "lever": ("jobs.lever.co",),
    "ashby": ("ashbyhq.com",),
    "workable": ("workable.com",),
    "jazzhr": ("applytojob.com",),
    "breezy": ("breezy.hr",),
    "recruitee": ("recruitee.com",),
    "bamboohr": ("bamboohr.com",),
}

# (pattern, profile key) - matched against label/placeholder/name/aria-label text.
# Order matters: first match wins. "__first/__last/__cover" are synthesized.
FIELD_RULES = [
    (r"first\s*name", "__first"),
    (r"(last|family)\s*name|surname", "__last"),
    (r"full\s*name|your\s*name|\bname\b", "name"),
    (r"e-?mail", "email"),
    (r"phone|mobile", "phone"),
    (r"linkedin", "linkedin"),
    (r"github", "github"),
    (r"website|portfolio|personal\s*site", "website"),
    (r"location|city|current\s*address", "location"),
    (r"cover\s*letter|why\s+(do\s+you|are\s+you|.*company)|additional\s*info|comments|anything\s*else", "__cover"),
]


def detect_ats(url):
    u = (url or "").lower()
    for name, hosts in ATS_HOSTS.items():
        if any(h in u for h in hosts):
            return name
    return None


def _values(profile, cover_letter_text):
    name = (profile.get("name") or "").strip()
    parts = name.split()
    vals = dict(profile)
    vals["__first"] = parts[0] if parts else ""
    vals["__last"] = " ".join(parts[1:]) if len(parts) > 1 else ""
    vals["__cover"] = cover_letter_text
    return vals


def _descriptor(page, handle):
    """Best-effort human label for a form element."""
    bits = []
    try:
        el_id = handle.get_attribute("id")
        if el_id:
            lab = page.locator(f'label[for="{el_id}"]')
            if lab.count():
                bits.append(lab.first.inner_text())
        for attr in ("placeholder", "name", "aria-label", "id", "autocomplete"):
            v = handle.get_attribute(attr)
            if v:
                bits.append(v)
        parent_label = handle.evaluate(
            "e => { const l = e.closest('label'); return l ? l.innerText : '' }")
        if parent_label:
            bits.append(parent_label)
    except Exception:
        pass
    return " ".join(bits).lower()


# Fields a bot must never touch: EEO/demographic self-identification is the
# human's call, and mis-filling it misreports protected characteristics.
NEVER_FILL = re.compile(r"hispanic|latino|gender|veteran|disab|race|ethnic|self.?identif", re.I)


def _fill_fields(page, vals):
    filled = []
    for handle in page.locator("input, textarea").element_handles():
        try:
            typ = (handle.get_attribute("type") or "text").lower()
            if typ in ("hidden", "checkbox", "radio", "submit", "button", "file", "search"):
                continue
            # custom dropdowns (comboboxes) need an option pick, not free text
            if (handle.get_attribute("role") == "combobox"
                    or handle.get_attribute("aria-autocomplete")
                    or handle.get_attribute("aria-haspopup")):
                continue
            if handle.input_value():
                continue  # respect anything pre-filled
            desc = _descriptor(page, handle)
            if not desc or NEVER_FILL.search(desc):
                continue
            for pat, key in FIELD_RULES:
                val = vals.get(key, "")
                if val and re.search(pat, desc):
                    handle.fill(str(val))
                    filled.append(key.strip("_"))
                    break
        except Exception:
            continue
    return filled


def _upload_resume(page, resume_file):
    if not resume_file or not Path(resume_file).exists():
        return False
    handles = page.locator('input[type="file"]').element_handles()
    best = None
    for h in handles:
        desc = _descriptor(page, h)
        if re.search(r"resume|cv", desc):
            best = h
            break
    if best is None and handles:
        best = handles[0]
    if best is None:
        return False
    try:
        best.set_input_files(resume_file)
        page.wait_for_timeout(2500)  # let async upload finish
        return True
    except Exception:
        return False


def _visible_captcha(page):
    sel = ('iframe[src*="recaptcha/api2/anchor"], .g-recaptcha, '
           'iframe[src*="hcaptcha"], .h-captcha, [data-captcha]')
    try:
        for h in page.locator(sel).element_handles():
            if h.is_visible():
                return True
    except Exception:
        pass
    return False


def _unfilled_required(page):
    out = []
    radio_groups = {}  # name -> [any_checked, descriptor]; required radios satisfy per group
    for handle in page.locator("input, textarea, select").element_handles():
        try:
            typ = (handle.get_attribute("type") or "text").lower()
            if typ in ("hidden", "submit", "button", "file"):
                continue
            req = handle.get_attribute("required")
            aria = handle.get_attribute("aria-required")
            if req is None and aria != "true":
                continue
            tag = handle.evaluate("e => e.tagName.toLowerCase()")
            if typ == "radio":
                name = handle.get_attribute("name") or _descriptor(page, handle)[:40]
                grp = radio_groups.setdefault(name, [False, _descriptor(page, handle)[:60]])
                if handle.is_checked():
                    grp[0] = True
            elif typ == "checkbox":
                if not handle.is_checked():
                    out.append(_descriptor(page, handle)[:60])
            elif tag == "select":
                v = handle.evaluate("e => e.value")
                if not v:
                    out.append(_descriptor(page, handle)[:60])
            elif not handle.input_value():
                out.append(_descriptor(page, handle)[:60])
        except Exception:
            continue
    for _, (checked, desc) in radio_groups.items():
        if not checked:
            out.append(desc)
    return out


def _reveal_form(page, ats):
    """Some boards hide the form behind an Apply button."""
    if page.locator('input[type="file"]').count():
        return
    try:
        btn = page.get_by_role("button", name=re.compile(r"apply", re.I)).first
        if btn.is_visible():
            btn.click()
            page.wait_for_timeout(2500)
            return
    except Exception:
        pass
    try:
        link = page.get_by_role("link", name=re.compile(r"apply", re.I)).first
        if link.is_visible():
            link.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
    except Exception:
        pass


def _assisted_loop(page, vals, resume_file):
    """Keep auto-filling as the human clicks through pages (Workday-style flows).
    Ends when the human presses Enter in the terminal or closes the browser."""
    print("[apply] Assisted mode: I auto-fill what I can on every page as it loads.")
    print("[apply] You: create the account if asked, click through, answer custom")
    print("[apply] questions, and submit. Press Enter HERE when done (or close the browser).")
    try:
        import msvcrt  # Windows console; elsewhere fall back to one blocking prompt
    except ImportError:
        _fill_fields(page, vals)
        _upload_resume(page, resume_file)
        input("[apply] Press Enter when done...")
        return
    for _ in range(1800):  # ~60 min cap
        try:
            _fill_fields(page, vals)
            _upload_resume(page, resume_file)
            page.wait_for_timeout(2000)
        except Exception:
            break  # browser closed or page gone
        while msvcrt.kbhit():
            if msvcrt.getwch() in ("\r", "\n"):
                return


def apply_to(job, profile, cover_letter_text="", resume_file="", auto=False,
             headful=False, shot_dir="data/screenshots"):
    """Returns (status, note). Statuses: ready | applied | needs_human."""
    url = job.get("url") or ""
    ats = detect_ats(url)
    if not ats and not headful:
        return ("needs_human", f"This site's form is not one jobbot can fill unattended. Apply manually with your tailored letter, or use assisted mode (apply --headful): {url}")

    Path(shot_dir).mkdir(parents=True, exist_ok=True)
    shot = str(Path(shot_dir) / f"{job['id'][:8]}.png")
    if ats == "lever" and not url.rstrip("/").endswith("/apply"):
        url = url.rstrip("/") + "/apply"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not headful)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            _reveal_form(page, ats)
            vals = _values(profile, cover_letter_text)
            filled = _fill_fields(page, vals)
            uploaded = _upload_resume(page, resume_file)
            captcha = _visible_captcha(page)
            missing = _unfilled_required(page)
            page.screenshot(path=shot, full_page=True)

            note_bits = [f"filled: {', '.join(sorted(set(filled))) or 'nothing'}",
                         f"resume upload: {'ok' if uploaded else 'FAILED'}"]
            if missing:
                note_bits.append(f"{len(missing)} required fields still blank: {'; '.join(missing[:3])}")
            if captcha:
                note_bits.append("visible CAPTCHA present")
            note_bits.append(f"screenshot: {shot}")
            note = " | ".join(note_bits)

            if headful and not auto:
                print(f"[apply] {job['title']} at {job['company']}")
                print(f"[apply] {note}")
                _assisted_loop(page, vals, resume_file)
                try:
                    page.screenshot(path=shot, full_page=True)
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass
                ans = input("[apply] Did you submit this application? [y/N] ").strip().lower()
                if ans == "y":
                    return ("applied", "submitted in assisted session | " + note)
                return ("needs_human", f"assisted session ended without submitting - finish at {url} | " + note)

            if not auto:
                browser.close()
                return ("ready", "dry run - nothing submitted | " + note)

            if captcha:
                browser.close()
                return ("needs_human", "CAPTCHA blocks auto-submit | " + note)
            if missing:
                browser.close()
                return ("needs_human", "required custom questions blank - submit manually | " + note)

            btn = page.locator('button[type="submit"], input[type="submit"]').first
            if not btn.count():
                btn = page.get_by_role("button", name=re.compile(r"submit|apply", re.I)).first
            btn.click()
            page.wait_for_timeout(6000)
            body = ""
            try:
                body = page.inner_text("body")
            except Exception:
                pass
            page.screenshot(path=shot, full_page=True)
            browser.close()
            if re.search(r"thank|received|submitted|success|we'll be in touch", body, re.I):
                return ("applied", "auto-submitted, confirmation detected | " + note)
            return ("needs_human", "submit clicked but no confirmation detected - verify manually | " + note)
    except Exception as e:
        return ("needs_human", f"automation error: {e.__class__.__name__}: {e}")
