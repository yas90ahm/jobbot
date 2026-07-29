"""LLM access with pluggable providers - defaults to the local Claude Code CLI.

Provider config lives in data/llm.json (edited from the dashboard's AI settings):
  {"provider": ..., "base_url": "...", "api_key": "...", "model": "..."}
Providers: claude-cli (default, no key needed), anthropic (API key),
and openai / ollama / custom - all three speak the OpenAI-compatible chat API,
which covers OpenAI, OpenRouter, Groq, and local models via Ollama or LM Studio.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import requests

CONFIG_PATH = Path("data/llm.json")
DEFAULTS = {"provider": "claude-cli", "base_url": "", "api_key": "", "model": ""}
PRESET_BASE_URLS = {"ollama": "http://localhost:11434/v1",
                    "openai": "https://api.openai.com/v1"}


def get_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps({k: cfg.get(k, "") for k in DEFAULTS}, indent=1), encoding="utf-8")


def _claude_cli(prompt, system, model, timeout):
    p = shutil.which("claude") or shutil.which("claude.cmd")
    if not p:
        if os.environ.get("ANTHROPIC_API_KEY"):
            return _anthropic(prompt, system, model, timeout,
                              os.environ["ANTHROPIC_API_KEY"])
        raise RuntimeError(
            "Claude Code is not set up on this computer. In the dashboard's "
            "AI settings pick another option: Ollama (free local model) or "
            "OpenAI/Anthropic with an API key. Or ask a technical friend to "
            "install Claude Code (npm i -g @anthropic-ai/claude-code).")
    argv = [p, "-p", "--model", model or "claude-sonnet-5", "--output-format", "text"]
    if p.lower().endswith((".cmd", ".bat")):
        # CreateProcess cannot exec batch files directly on Windows.
        argv = ["cmd", "/c"] + argv
    full_text = (system + "\n\n" + prompt) if system else prompt
    result = subprocess.run(argv, input=full_text, capture_output=True,
                            text=True, encoding="utf-8", timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited with code {result.returncode}: {result.stderr[-500:]}")
    return result.stdout.strip()


def _anthropic(prompt, system, model, timeout, api_key):
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model or "claude-sonnet-5", "max_tokens": 4000,
              "system": system or "You are a helpful assistant.",
              "messages": [{"role": "user", "content": prompt}]},
        timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text[:300]}")
    return "".join(b.get("text", "") for b in resp.json()["content"]).strip()


def _openai_compatible(prompt, system, model, timeout, base_url, api_key):
    base = (base_url or "https://api.openai.com/v1").rstrip("/")
    messages = ([{"role": "system", "content": system}] if system else []) \
        + [{"role": "user", "content": prompt}]
    headers = {"content-type": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    try:
        resp = requests.post(f"{base}/chat/completions", headers=headers,
                             json={"model": model, "messages": messages},
                             timeout=timeout)
    except requests.ConnectionError:
        raise RuntimeError(
            f"Could not reach {base} - is the server running? "
            "(for Ollama: run 'ollama serve' and 'ollama pull <model>')")
    if resp.status_code == 404 and "not found" in resp.text.lower():
        raise RuntimeError(
            f"Model '{model}' is not installed on {base}. "
            f"For Ollama, run: ollama pull {model}")
    if resp.status_code != 200:
        raise RuntimeError(f"LLM API error {resp.status_code} from {base}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"].strip()


def ask(prompt: str, system: str = "", model: str = None, timeout: int = 240) -> str:
    cfg = get_config()
    provider = cfg.get("provider") or "claude-cli"
    if provider == "anthropic":
        key = cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Anthropic API selected but no API key set - "
                               "add one in the dashboard's AI settings.")
        return _anthropic(prompt, system, cfg.get("model"), timeout, key)
    if provider in ("openai", "ollama", "custom"):
        if not cfg.get("model"):
            raise RuntimeError(
                "No model name set - add one in AI settings "
                "(e.g. llama3.1 for Ollama, gpt-4o-mini for OpenAI).")
        base = cfg.get("base_url") or PRESET_BASE_URLS.get(provider, "")
        return _openai_compatible(prompt, system, cfg["model"], timeout,
                                  base, cfg.get("api_key"))
    return _claude_cli(prompt, system, model or cfg.get("model"), timeout)


def _extract_json(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    m = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def ask_json(prompt: str, system: str = "", model: str = None, timeout: int = 240) -> dict:
    reply = ask(prompt, system=system, model=model, timeout=timeout)
    data = _extract_json(reply)
    if data is not None:
        return data

    reply = ask(prompt + "\n\nReturn ONLY valid JSON, no prose.",
                system=system, model=model, timeout=timeout)
    data = _extract_json(reply)
    if data is not None:
        return data

    raise RuntimeError(f"LLM did not return valid JSON: {reply[:300]}")
