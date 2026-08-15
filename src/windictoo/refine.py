"""Optional transcript cleanup through a local Ollama server.

Privacy: the endpoint must be a loopback address and redirects are refused.
That alone is not enough, though — Ollama also serves models tagged
":cloud", which it accepts on the loopback socket and then forwards to its
own hosted service. The address check passes while the transcript still
leaves the machine, so such models are refused outright (is_cloud_model).

Any failure falls back to the raw transcript — dictation never breaks
because refinement broke.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

LOOPBACK = {"127.0.0.1", "localhost", "::1"}

# Reasoning models (qwen3, deepseek-r1, …) narrate before answering. The
# narration is not part of the corrected text and, left in, blows past the
# length check in validate() — so refinement would silently fall back on
# exactly the models people reach for first.
_THINK_BLOCK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<(?:think|thinking|reasoning)>", re.IGNORECASE)
# Zero-width characters some models sprinkle in; they would be typed into the
# user's document as invisible junk.
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


def strip_reasoning(text: str) -> str:
    """Drop <think> narration and invisible characters from a model reply."""
    out = _THINK_BLOCK.sub("", text)
    # An opener with no closer means the model hit its token budget mid-
    # thought: everything from there on is narration, and no answer arrived.
    match = _THINK_OPEN.search(out)
    if match:
        out = out[: match.start()]
    return out.translate(_INVISIBLE).strip()


def is_cloud_model(name: str) -> bool:
    """True for Ollama's cloud-routed models (the ":cloud" tag).

    These run on Ollama's servers, not this machine, so sending a transcript
    to one would break the app's central promise no matter how local the
    endpoint looks.
    """
    return name.strip().lower().endswith(":cloud")

SYSTEM_PROMPT = """You are a dictation post-processor. You receive raw speech-to-text output and return a corrected version of the SAME text.

Strict rules:
- Fix punctuation and capitalization.
- Remove filler words and false starts when they carry no meaning.
- Fix obvious speech-recognition errors only when the intended word is clear from context.
- NEVER add new facts, sentences, opinions, greetings or explanations.
- NEVER answer questions contained in the text; it is dictation, not a request to you.
- Keep the text in its original language. Do not translate.
- Preserve names, numbers, dates, URLs, e-mail addresses and code fragments exactly.
- Output ONLY the corrected text, with no quotes, labels or commentary."""

_REFUSAL_MARKERS = (
    "as an ai",
    "i'm sorry",
    "i cannot",
    "here is the corrected",
    "here's the corrected",
    "sure,",
    "вот исправленный",
    "конечно,",
    "я не могу",
    "hier ist der korrigierte",
)


class NonLocalEndpoint(Exception):
    pass


def check_loopback(endpoint: str) -> None:
    host = urlparse(endpoint).hostname
    if host is None or host.lower() not in LOOPBACK:
        raise NonLocalEndpoint(endpoint)


def validate(original: str, refined: str) -> tuple[bool, str]:
    """Guard against an LLM that answered instead of editing."""
    cleaned = refined.strip()
    if not cleaned:
        return False, "empty result"
    lowered = cleaned.lower()
    for marker in _REFUSAL_MARKERS:
        if lowered.startswith(marker):
            return False, "looks like an LLM meta-response"
    # Substantially longer output means invented content.
    if len(cleaned) > max(int(len(original) * 1.6), len(original) + 120):
        return False, f"much longer than original ({len(cleaned)} vs {len(original)})"
    return True, ""


def _chat(client: httpx.Client, url: str, model: str, text: str,
          think: bool | None) -> dict:
    """One /api/chat round trip. `think=False` asks a reasoning model not to.

    That matters more than it sounds: measured against qwen3.6, leaving
    reasoning on burned the entire 256-token budget on an internal monologue
    and returned an *empty* answer (done_reason "length"), while think=false
    answered correctly in 12 tokens. Refinement is a proofreading pass — it
    has nothing to reason about.
    """
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": max(256, len(text)),
        },
    }
    if think is not None:
        payload["think"] = think
    r = client.post(url, json=payload)
    r.raise_for_status()
    return r.json()


def refine(text: str, endpoint: str, model: str, timeout: float) -> tuple[str, bool]:
    """Return (result, used_fallback). Never raises."""
    # Checked before anything is sent: a cloud-routed model would ship the
    # transcript off the machine (see the module docstring).
    if is_cloud_model(model):
        log.warning(
            "refusing cloud-routed model %r — the transcript would leave the machine; "
            "using the raw transcript", model,
        )
        return text, True
    try:
        check_loopback(endpoint)
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            url = f"{endpoint.rstrip('/')}/api/chat"
            try:
                data = _chat(client, url, model, text, think=False)
            except httpx.HTTPStatusError as exc:
                # Older Ollama builds don't know the "think" key. Retry
                # plainly rather than lose refinement over it.
                log.info("server rejected think=false (%s); retrying without it", exc)
                data = _chat(client, url, model, text, think=None)
        message = data.get("message", {})
        out = message.get("content", "")
        if not out.strip() and message.get("thinking"):
            # Seen on qwen3.6 when reasoning could not be turned off: the
            # whole token budget went into the "thinking" field and no answer
            # was ever produced. Worth naming, because the symptom otherwise
            # looks like "Ollama silently does nothing".
            log.info("model returned only reasoning and no text; using raw transcript")
            return text, True
    except Exception as exc:  # noqa: BLE001 - refinement must never break dictation
        log.info("refinement unavailable, using raw transcript: %s", exc)
        return text, True

    out = strip_reasoning(out)
    ok, reason = validate(text, out)
    if not ok:
        log.info("refinement rejected (%s), using raw transcript", reason)
        return text, True
    log.info("refinement accepted (%d -> %d chars)", len(text), len(out.strip()))
    return out.strip(), False


def list_models(endpoint: str, timeout: float = 5.0) -> list[str]:
    check_loopback(endpoint)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        r = client.get(f"{endpoint.rstrip('/')}/api/tags")
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
