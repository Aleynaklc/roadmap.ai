"""Build the static GitHub Pages version of the FastAPI frontend."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "pages"


def replace_required(source: str, old: str, new: str) -> str:
    if old not in source:
        raise RuntimeError(f"Expected template content was not found: {old}")
    return source.replace(old, new)


def build() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    for directory in ("data", "lessons", "static"):
        shutil.copytree(
            ROOT / directory,
            OUTPUT / directory,
            ignore=shutil.ignore_patterns(".DS_Store"),
        )

    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    replacements = (
        (
            "{{ url_for('static', path='css/styles.css') }}",
            "static/css/styles.css",
        ),
        (
            '<script type="module" src="{{ url_for(\'static\', path=\'js/app.js\') }}"></script>',
            '<script>window.APP_CONFIG = { staticSite: true };</script>\n'
            '<script type="module" src="static/js/app.js"></script>',
        ),
        ("AI Engineer Roadmap — Python Backend Edition", "AI Engineer Roadmap"),
        ("✦ FastAPI Powered", "✦ GitHub Pages Edition"),
        (
            "A Python-backend clone of the roadmap. Lesson content is served through FastAPI endpoints while preserving the original UI and content.",
            "An interactive AI engineering roadmap with 41 lessons, progress tracking, bookmarks, and search.",
        ),
        (
            '<button class="btn-sm btn-outline" type="button">Python Backend</button>',
            '<button class="btn-sm btn-outline" type="button">Interactive Roadmap</button>',
        ),
        ("<div class=\"stat-n\">API</div><div class=\"stat-l\">Lesson Loading</div>",
         "<div class=\"stat-n\">41</div><div class=\"stat-l\">Lessons</div>"),
        ("<div class=\"stat-n\">Python</div><div class=\"stat-l\">Backend</div>",
         "<div class=\"stat-n\">100%</div><div class=\"stat-l\">Free</div>"),
        ("<div class=\"tutor-status\">● Python Backend</div>",
         "<div class=\"tutor-status\">● Local backend required</div>"),
        (
            "Hi! I’m served by FastAPI now. Open a lesson and ask anything about it.",
            "Lesson chat is available when the FastAPI project is run locally.",
        ),
    )
    for old, new in replacements:
        html = replace_required(html, old, new)

    if "{{" in html or "}}" in html:
        raise RuntimeError("Unrendered template syntax remains in index.html")

    (OUTPUT / "index.html").write_text(html, encoding="utf-8")
    (OUTPUT / ".nojekyll").touch()

    roadmap = json.loads((OUTPUT / "data" / "roadmap.json").read_text(encoding="utf-8"))
    metadata = json.loads((OUTPUT / "data" / "lesson_meta.json").read_text(encoding="utf-8"))
    lesson_ids = {node["id"] for stage in roadmap for node in stage["nodes"]}
    if lesson_ids != set(metadata):
        raise RuntimeError("Roadmap and lesson metadata IDs do not match")
    for lesson_id, entry in metadata.items():
        lesson_file = OUTPUT / "lessons" / entry["file"]
        if not lesson_file.is_file():
            raise RuntimeError(f"Missing lesson file for {lesson_id}: {lesson_file.name}")

    print(f"Built GitHub Pages site with {len(lesson_ids)} lessons in {OUTPUT}")


if __name__ == "__main__":
    build()
