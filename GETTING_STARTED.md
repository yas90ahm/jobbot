# Getting jobbot running (literal step by step)

Find your situation below. All three end the same way: a jobbot dashboard open
in your browser. Windows instructions; on a Mac use Terminal instead of Command
Prompt and `python3` instead of `python`.

---

## A. "I already use Claude on my computer"

1. Press the **Windows key**, type `cmd`, press **Enter**. A black window opens.
2. Type `claude` and press **Enter**.
3. Copy this, paste it into the window, press **Enter**:

   ```
   Clone https://github.com/yas90ahm/jobbot into a folder called jobbot,
   run its setup.bat, and when it finishes start it with start_jobbot.bat
   ```

4. Claude asks permission before each step - say yes. When the dashboard opens
   in your browser, you're done. Claude is also jobbot's default AI, so
   everything works with no further setup.

(Have a Claude subscription but never installed Claude Code? First install
Node.js from https://nodejs.org - big green LTS button, Next through
everything - then in the black window run `npm install -g @anthropic-ai/claude-code`,
then start at step 2.)

## B. "I use ChatGPT, not Claude"

You'll use OpenAI's Codex CLI - the ChatGPT version of the same idea. It needs
a paid ChatGPT plan (Plus or higher).

1. Install **Node.js**: https://nodejs.org, big green LTS button, run it,
   Next through everything.
2. Press the **Windows key**, type `cmd`, press **Enter**.
3. Paste this and press **Enter**:

   ```
   npm install -g @openai/codex
   ```

4. Type `codex` and press **Enter**, and sign in with your ChatGPT account
   when it asks.
5. Paste the same ask:

   ```
   Clone https://github.com/yas90ahm/jobbot into a folder called jobbot,
   run its setup.bat, and when it finishes start it with start_jobbot.bat
   ```

6. One extra step: jobbot needs an AI of its own for resume work, and a
   ChatGPT login does not cover that. On the dashboard open **AI settings**
   and pick one:
   - **Ollama** - completely free, runs on your computer. Install from
     https://ollama.com, then in Command Prompt run `ollama pull llama3.1`.
     In AI settings choose Ollama, type `llama3.1` as the model, click
     **Save and test** until it says Working.
   - **OpenAI API key** - paid separately from ChatGPT Plus, from
     https://platform.openai.com. Choose OpenAI, paste the key, Save and test.

## C. "I have neither" (all free, no accounts needed)

1. Install **Python**: https://www.python.org/downloads, click Download, run
   it. **IMPORTANT: tick the checkbox "Add python.exe to PATH"** before
   clicking Install.
2. Get the code - either way works:
   - Go to https://github.com/yas90ahm/jobbot, click the green **Code**
     button, **Download ZIP**, right-click the ZIP, **Extract All**, and
     remember where you put the folder. Skip to step 4.
   - Or install Git from https://git-scm.com/downloads (all defaults), then
     do step 3.
3. Press the **Windows key**, type `cmd`, **Enter**, then paste these one at
   a time, pressing **Enter** after each:

   ```
   cd %USERPROFILE%\Desktop
   git clone https://github.com/yas90ahm/jobbot
   cd jobbot
   setup.bat
   ```

   (If you downloaded the ZIP instead: type `cd ` then drag the extracted
   folder onto the black window, press Enter, then type `setup.bat`, Enter.)
4. When it says "Done!", double-click **`start_jobbot.bat`** in the jobbot
   folder. The dashboard opens in your browser.
5. Give jobbot its free AI: install **Ollama** from https://ollama.com, then
   in Command Prompt run `ollama pull llama3.1`. On the dashboard open
   **AI settings**, choose Ollama, type `llama3.1` as the model, click
   **Save and test** until it says Working.

## D. "I have an API key for some LLM"

Any provider works - OpenAI, Anthropic, Groq, OpenRouter, DeepSeek, Together,
or anything else that speaks the standard OpenAI-style API.

1. Get the code running: do **steps 1-4 of Path C** above (install Python,
   download the code, run setup.bat, start it).
2. On the dashboard open **AI settings** and match your key:
   - **OpenAI key** (starts with `sk-`): choose "OpenAI API", paste the key,
     type a model name like `gpt-4o-mini`.
   - **Anthropic key** (starts with `sk-ant-`): choose "Anthropic API", paste
     the key, leave the model blank.
   - **Anything else** (Groq, OpenRouter, DeepSeek, Together, a company
     server...): choose "Custom OpenAI-compatible server", paste the key, put
     the provider's base URL in "Server URL" (examples:
     `https://openrouter.ai/api/v1`, `https://api.groq.com/openai/v1`,
     `https://api.deepseek.com/v1`), and type the model name exactly as the
     provider lists it.
3. Click **Save and test** until it says **Working**. That's it - the key is
   stored only on your computer.

---

## First use (everyone)

0. **AI first**: if you came via Path B, C, or D, make sure **AI settings** on
   the dashboard says **Working** before anything else - the Analyze step and
   all resume work need it. (Path A people are already set.)
1. On the dashboard, upload your resume and click **"Analyze resume first"**.
2. A card appears showing what the AI understood: your contact info, the job
   titles it will search for, your skills. **Fix anything wrong** (missing
   phone number, a title you don't want) and click **Save corrections**.
3. Type your location, leave keywords blank, click **Run**. Come back in
   20 minutes and work through "Your to-do list".
4. From then on: double-click `start_jobbot.bat`, hit Run, review, apply.

Full usage guide: [HOW_TO_USE.md](HOW_TO_USE.md)
