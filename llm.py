"""
llm.py
------
Talks to the local Ollama server (Qwen) and returns plain text.

Everything runs on the RTX machine where Ollama is already running, so we
just use localhost. No cloud, no API key, no quota, unlimited calls, and
the data never leaves the machine.

Settings (from .env, with sensible defaults):
    OLLAMA_URL=http://localhost:11434
    OLLAMA_MODEL=qwen2.5:32b
"""

import os
import json
import time
import urllib.request
import urllib.error

MAX_TRIES = 3
BASE_WAIT_SECONDS = 3

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


def generate(model: str, prompt: str, max_output_tokens: int) -> str:
    """Send a prompt to local Qwen via Ollama and return the text response."""
    url = f"{OLLAMA_URL}/api/generate"

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_ctx": 4096,            # important: default 131072 wastes ~58GB VRAM
            "num_predict": max_output_tokens,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    last_error = None
    for attempt in range(1, MAX_TRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["response"]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_error = e
            if attempt < MAX_TRIES:
                wait = BASE_WAIT_SECONDS * attempt
                print(f"    Ollama not responding. Waiting {wait}s, retrying ({attempt}/{MAX_TRIES})...")
                time.sleep(wait)

    raise RuntimeError(
        f"Ollama did not respond after {MAX_TRIES} tries. "
        f"Is Ollama running at {OLLAMA_URL}?  (try: ollama list)\nError: {last_error}"
    ) from last_error