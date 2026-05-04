# Hyperwrite

A local writing studio with a FastAPI backend, Preact frontend, shadcn/ui-style components, Markdown persistence, and an OpenRouter-powered LangGraph workflow.

## Features

- Generate written pieces from a prompt and optional `.md` / `.txt` source files.
- Save every completed piece as clean article Markdown in `data/pieces`.
- Save reviewer notes separately in `data/reviews` with generation metadata beside each piece.
- Use OpenRouter for all model calls.
- Draft with a writer agent, review with a reviewer agent, and revise before presenting.
- Optionally add a research agent that uses Perplexity through OpenRouter.
- Optionally apply the bundled anti-AI writing style guide for more direct, human-sounding prose.
- Anti AI Style guide by  https://ruben.substack.com/

## Setup

```bash
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
pip install -e ./backend
npm install --prefix frontend
```

Set `OPENROUTER_API_KEY` in `.env`.

## Run

Backend:

```bash
. .venv/bin/activate
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
npm run dev --prefix frontend
```

Open the Vite URL, usually `http://127.0.0.1:5173`.

## Notes

- Writer and reviewer defaults are configured in `.env.example`.
- The research model defaults to `perplexity/sonar-pro-search`.
- API output includes the final Markdown, review notes, and saved Markdown path.
