# AI Roadmap Python Backend

This is a separate FastAPI-based clone of the existing roadmap project.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

## What was copied

- lesson HTML files from the existing project into `lessons/`
- roadmap structure into `data/roadmap.json`
- lesson metadata into `data/lesson_meta.json`
- styles into `static/css/styles.css`

## API

- `GET /api/roadmap`
- `GET /api/lesson/{slug}`
- `POST /api/chat`

`/api/chat` is currently a backend stub. It is ready to be connected to Gemini, OpenAI, Anthropic, or a local model later.
# roadmap.ai
