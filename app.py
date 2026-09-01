from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from chatbot.llm import stream_chat_completion
from chatbot.memory import add_message, clear_session, get_history
from chatbot.prompts import build_system_prompt


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LESSONS_DIR = BASE_DIR / "lessons"


def load_json(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


STAGES = load_json("roadmap.json")
LESSON_META = load_json("lesson_meta.json")


class ChatPayload(BaseModel):
    message: str
    lesson_title: str | None = None
    stage_label: str | None = None
    session_id: str | None = None


app = FastAPI(title="AI Roadmap Python Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/lessons", StaticFiles(directory=str(LESSONS_DIR)), name="lessons")

_RATE_LIMIT: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW_S = 60
_RATE_LIMIT_MAX_REQ = 30


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_or_429(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    bucket = _RATE_LIMIT.setdefault(ip, [])
    cutoff = now - _RATE_LIMIT_WINDOW_S
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= _RATE_LIMIT_MAX_REQ:
        raise HTTPException(status_code=429, detail="Too many chat requests. Please wait a moment.")
    bucket.append(now)


def _strip_html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _load_lesson_text_by_title(title: str | None) -> str | None:
    if not title:
        return None
    # Best-effort: match node title -> slug from STAGES
    title_norm = title.strip().lower()
    slug = None
    for stage in STAGES:
        for node in stage["nodes"]:
            if str(node.get("title", "")).strip().lower() == title_norm:
                slug = node.get("id")
                break
        if slug:
            break
    if not slug:
        return None
    lesson_meta = LESSON_META.get(slug)
    if not lesson_meta:
        return None
    lesson_path = LESSONS_DIR / lesson_meta["file"]
    if not lesson_path.exists():
        return None
    raw_html = lesson_path.read_text(encoding="utf-8")
    return _strip_html_to_text(raw_html)


def find_node(slug: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for stage in STAGES:
        for node in stage["nodes"]:
            if node["id"] == slug:
                return stage, node
    raise HTTPException(status_code=404, detail=f"Unknown lesson slug: {slug}")


def build_default_lesson(node: dict[str, Any], stage: dict[str, Any]) -> dict[str, str]:
    return {
        "stage": stage["label"],
        "stageColor": stage["color"],
        "content": f"""
<h2><span class="h2-num" style="background:rgba(100,116,139,.15);color:#94a3b8">1</span> Overview</h2>
<p>This topic — <strong>{node["title"]}</strong> — is an essential part of your AI Engineering journey. Full deep-dive content is being crafted for this section. Below is a preview of what you'll learn.</p>

<div class="callout">✦ <strong>Coming soon:</strong> A full 1500+ word lesson with code examples, diagrams, interview questions, and practice tasks for {node["title"]}.</div>

<h2><span class="h2-num" style="background:rgba(100,116,139,.15);color:#94a3b8">2</span> Key Concepts</h2>
<p>When you study <strong>{node["title"]}</strong>, you'll need to understand: the fundamental theory behind it, how it's applied in real AI systems, common pitfalls practitioners encounter, and how to implement it in Python.</p>

<h2><span class="h2-num" style="background:rgba(100,116,139,.15);color:#94a3b8">3</span> Why AI Engineers Need This</h2>
<p>Every modern AI engineer encounters <strong>{node["title"]}</strong> in production systems. Whether you're building RAG pipelines, deploying models, or working with multimodal data — this concept will appear regularly in your work.</p>

<div class="callout warn">📚 <strong>While full content loads:</strong> Search for "{node["title"]}" on Hugging Face, Papers With Code, or the official PyTorch docs to start learning now.</div>

<h2><span class="h2-num" style="background:rgba(100,116,139,.15);color:#94a3b8">4</span> Practice Tasks</h2>
<ul class="task-list" id="tasks-default-{node["id"]}">
  <li data-task-toggle>Read the Wikipedia article on {node["title"]} and summarize it in your own words</li>
  <li data-task-toggle>Find a Python implementation on GitHub and run it locally</li>
  <li data-task-toggle>Search for a tutorial on YouTube and code along</li>
</ul>
""".strip(),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/roadmap")
async def roadmap() -> dict[str, Any]:
    return {"stages": STAGES}


@app.get("/api/lesson/{slug}")
async def lesson(slug: str) -> dict[str, Any]:
    stage, node = find_node(slug)
    lesson_meta = LESSON_META.get(slug)
    if not lesson_meta:
        return build_default_lesson(node, stage)

    lesson_path = LESSONS_DIR / lesson_meta["file"]
    if not lesson_path.exists():
        raise HTTPException(status_code=404, detail=f"Lesson file missing for slug: {slug}")

    return {
        "stage": lesson_meta["stage"],
        "stageColor": lesson_meta["stageColor"],
        "content": lesson_path.read_text(encoding="utf-8"),
        "node": node,
        "stageInfo": stage,
    }


@app.post("/api/chat")
async def chat(payload: ChatPayload, request: Request):
    _rate_limit_or_429(request)

    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message is required.")
    if len(message) > 4000:
        raise HTTPException(status_code=422, detail="Message too long (max 4000 chars).")

    session_id = payload.session_id or str(uuid.uuid4())

    lesson_text = _load_lesson_text_by_title(payload.lesson_title)
    if lesson_text:
        # Keep prompt cost bounded
        lesson_text = lesson_text[:2500]

    system_prompt = build_system_prompt(
        lesson_title=payload.lesson_title,
        stage_label=payload.stage_label,
        lesson_content=lesson_text,
    )

    history = get_history(session_id)
    add_message(session_id, "user", message)

    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": message}]
    )

    def generate():
        full = []
        try:
            for chunk in stream_chat_completion(messages):
                full.append(chunk)
                yield chunk
        except Exception as e:
            yield f"\n\n[Error] {str(e)}"
        finally:
            if full:
                add_message(session_id, "assistant", "".join(full))

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Session-Id": session_id},
    )


@app.delete("/api/chat/{session_id}")
async def clear_chat(session_id: str):
    clear_session(session_id)
    return {"cleared": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
#source .venv/bin/activate
