from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request


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
async def chat(payload: ChatPayload) -> dict[str, str]:
    lesson_part = f" for {payload.lesson_title}" if payload.lesson_title else ""
    stage_part = f" in {payload.stage_label}" if payload.stage_label else ""
    return {
        "reply": (
            f"This Python backend project does not call an external model yet. "
            f"You asked{lesson_part}{stage_part}: \"{payload.message}\". "
            f"The next step is wiring this endpoint to Gemini, OpenAI, Anthropic, or a local model."
        )
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
#source .venv/bin/activate
