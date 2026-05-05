# Hyperwrite

Hyperwrite is a local writing studio that works as both a web app and a CLI. It includes a FastAPI backend, Preact frontend, shadcn/ui-style components, Markdown persistence, and an OpenRouter-powered LangGraph workflow.

## Features

- Generate written pieces from a prompt and optional `.md` / `.txt` source files.
- Save every completed piece as clean article Markdown in `data/pieces`.
- Save reviewer notes separately in `data/reviews` with generation metadata beside each piece.
- Use OpenRouter for all model calls.
- Draft with a writer agent, review with a reviewer agent, and revise before presenting.
- Optionally add a research agent that uses Perplexity through OpenRouter.
- Optionally apply the bundled anti-AI writing style guide for more direct, human-sounding prose.
- Optionally use Interview me mode to ask for missing context before writing.
- Use the same features from the browser or from the `hyperwrite` command.
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

## Run The Web App

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

## Use The CLI

Installing the backend with `pip install -e ./backend` adds the `hyperwrite` command. Run commands from the project root so `.env` and `data/pieces` resolve correctly.

List operations and usage:

```bash
hyperwrite help
hyperwrite help generate
hyperwrite generate --help
```

Generate and save a piece:

```bash
hyperwrite generate "Write a concise launch post for a local writing app"
```

Generate with source files, research, and the anti-AI style guide:

```bash
hyperwrite generate "Turn these notes into an article" \
  --source notes.md \
  --source outline.txt \
  --research \
  --anti-ai-style \
  --style "Clear, direct, no hype"
```

Generate with Interview me mode:

```bash
hyperwrite generate "Write a founder letter about our product launch" --interview
```

Manage saved pieces:

```bash
hyperwrite list
hyperwrite list --search launch
hyperwrite show <slug>
hyperwrite show <slug> --review
hyperwrite show <slug> --metadata
hyperwrite delete <slug> --yes
```

Revise saved pieces:

```bash
hyperwrite apply-review <slug>
hyperwrite follow-up <slug> "Make the intro shorter and add a stronger ending"
```

Inspect configuration:

```bash
hyperwrite models
hyperwrite health
```

Most commands support `--json` for machine-readable output. Generation and revision commands also support model overrides such as `--writer-model`, `--reviewer-model`, and `--research-model`.

## Notes

- Writer and reviewer defaults are configured in `.env.example`.
- The research model defaults to `perplexity/sonar-pro-search`.
- API and CLI output include the final Markdown path, review notes when requested, and saved metadata.
