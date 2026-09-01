from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from dotenv import load_dotenv


# Load variables from project-root .env (if present).
# This keeps local setup simple: users can set GROQ_API_KEY in .env without exporting it in the shell.
load_dotenv()


@dataclass(frozen=True)
class LLMConfig:
    provider: str  # "groq" | "ollama"
    model: str
    temperature: float = 0.7
    max_tokens: int = 800


def _pick_config() -> LLMConfig:
    forced = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if forced in {"groq", "ollama"}:
        if forced == "groq":
            return LLMConfig(provider="groq", model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        return LLMConfig(provider="ollama", model=os.getenv("OLLAMA_MODEL", "llama3.1"))

    # Preference order: GROQ (free-tier API) -> local Ollama (free, local compute)
    if os.getenv("GROQ_API_KEY"):
        return LLMConfig(provider="groq", model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    return LLMConfig(provider="ollama", model=os.getenv("OLLAMA_MODEL", "llama3.1"))


def stream_chat_completion(messages: list[dict]):
    cfg = _pick_config()
    if cfg.provider == "groq":
        yield from _stream_groq(messages, cfg)
        return
    yield from _stream_ollama(messages, cfg)


def _stream_groq(messages: list[dict], cfg: LLMConfig):
    try:
        from groq import Groq  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "GROQ_API_KEY is set but 'groq' package is not installed. Add 'groq' to requirements.txt."
        ) from e

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    try:
        stream = client.chat.completions.create(
            model=cfg.model,
            messages=messages,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as e:
        msg = str(e)
        if "invalid_api_key" in msg or "Invalid API Key" in msg or "Error code: 401" in msg:
            raise RuntimeError(
                "Groq returned 401 (Invalid API Key). Update GROQ_API_KEY in .env (or unset it to use Ollama), "
                "then restart the server."
            ) from e
        raise


def _stream_ollama(messages: list[dict], cfg: LLMConfig):
    # Ollama must be running locally: https://ollama.com
    # Streaming protocol is line-delimited JSON objects.
    url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
    payload = {
        "model": cfg.model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": cfg.temperature,
            "num_predict": cfg.max_tokens,
        },
    }
    req = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("done"):
                    break
                msg = obj.get("message") or {}
                content = msg.get("content")
                if content:
                    yield content
    except Exception as e:
        raise RuntimeError(
            "Local Ollama request failed. Ensure Ollama is running and the model is pulled "
            f"(provider=ollama, url={url}, model={cfg.model})."
        ) from e

