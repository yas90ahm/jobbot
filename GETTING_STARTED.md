# Getting jobbot running from zero (literal step by step)

Two paths. Path A lets Claude do the setup for you. Path B is classic copy-paste.
Both end with a dashboard in your browser. Windows instructions; on Mac, use
Terminal instead of Command Prompt and `python3` instead of `python`.

## Path A - let Claude Code set it up for you (easiest)

1. Install **Node.js**: go to https://nodejs.org and click the big green "LTS"
   download. Run the installer, click Next through everything.
2. Install **Python**: go to https://www.python.org/downloads and click Download.
   Run the installer. **IMPORTANT: tick the checkbox "Add python.exe to PATH"**
   before clicking Install.
3. Open **Command Prompt**: press the Windows key, type `cmd`, press Enter.
4. Install Claude Code. Paste this into the black window and press Enter:

   ```
   npm install -g @anthropic-ai/claude-code
   ```

5. Type `claude` and press Enter. The first time, it asks you to log in with
   your Claude account (a browser window opens - log in, come back).
6. Now literally ask Claude to do the rest. Paste this and press Enter:

   ```
   Clone https://github.com/yas90ahm/jobbot into a folder called jobbot,
   run its setup.bat, and when it finishes start it with start_jobbot.bat
   ```

7. Claude will ask permission before each command - approve them. When the
   jobbot dashboard opens in your browser, you are done.
8. From tomorrow on, skip all of this: just double-click **`start_jobbot.bat`**
   in the jobbot folder.

Bonus of Path A: Claude Code is also jobbot's default (free) AI, so the AI
features work immediately with no extra setup.

## Path B - without Claude Code

1. Install **Python** (step 2 above - do not forget the PATH checkbox).
2. Install **Git**: https://git-scm.com/downloads, install with all defaults.
   (No Git? On https://github.com/yas90ahm/jobbot click the green "Code"
   button, then "Download ZIP", unzip it, and skip to step 4.)
3. Open **Command Prompt** (Windows key, type `cmd`, Enter) and paste these
   one at a time, pressing Enter after each:

   ```
   cd %USERPROFILE%\Desktop
   git clone https://github.com/yas90ahm/jobbot
   cd jobbot
   setup.bat
   ```

4. When it says "Done!", type `start_jobbot.bat` and press Enter (or
   double-click that file in the folder). The dashboard opens in your browser.
5. Since you skipped Claude Code, open **AI settings** on the dashboard and
   pick your AI: **Ollama** (free, install from https://ollama.com then run
   `ollama pull llama3.1` in Command Prompt) or paste an **OpenAI/Anthropic
   API key**. Press "Save and test" until it says Working.

## First use (both paths)

1. On the dashboard, upload your resume and click **"Analyze resume first"**.
2. A card appears showing what the AI understood: your contact info, the job
   titles it will search for, skills. **Fix anything wrong** (missing phone
   number, wrong title) and click **Save corrections**.
3. Type your location, leave keywords blank, click **Run**. Come back in
   20 minutes and work through "Your to-do list".

Full usage guide: [HOW_TO_USE.md](HOW_TO_USE.md)
