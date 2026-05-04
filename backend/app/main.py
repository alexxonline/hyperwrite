from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .graph import build_graph
from .models import GenerationResponse, ModelDefaults, Piece, PieceSummary
from .storage import list_pieces, read_piece, save_piece


app = FastAPI(title="Hyperwrite API")


@app.on_event("startup")
async def _ensure_storage() -> None:
    get_settings().pieces_dir.mkdir(parents=True, exist_ok=True)


settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _read_uploads(files: list[UploadFile] | None) -> str:
    if not files:
        return ""
    chunks: list[str] = []
    for uploaded in files:
        suffix = Path(uploaded.filename or "").suffix.lower()
        if suffix not in {".md", ".markdown", ".txt"}:
            raise HTTPException(
                status_code=400,
                detail=f"{uploaded.filename} is not a supported text or Markdown file.",
            )
        raw = await uploaded.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"{uploaded.filename} must be UTF-8 encoded.",
            ) from exc
        chunks.append(f"## File: {uploaded.filename}\n\n{text.strip()}")
    return "\n\n".join(chunks)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config/models", response_model=ModelDefaults)
async def get_model_defaults(settings: Settings = Depends(get_settings)) -> ModelDefaults:
    return ModelDefaults(
        writer_model=settings.writer_model,
        reviewer_model=settings.reviewer_model,
        research_model=settings.research_model,
    )


@app.get("/api/pieces", response_model=list[PieceSummary])
async def get_pieces(settings: Settings = Depends(get_settings)) -> list[PieceSummary]:
    return list_pieces(settings.pieces_dir)


@app.get("/api/pieces/{slug}", response_model=Piece)
async def get_piece(slug: str, settings: Settings = Depends(get_settings)) -> Piece:
    try:
        return read_piece(settings.pieces_dir, slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Piece not found.") from exc


@app.post("/api/pieces", response_model=GenerationResponse)
async def create_piece(
    prompt: str = Form(...),
    use_research: bool = Form(False),
    style: str = Form(""),
    writer_model: str | None = Form(None),
    reviewer_model: str | None = Form(None),
    research_model: str | None = Form(None),
    files: list[UploadFile] | None = File(None),
    settings: Settings = Depends(get_settings),
) -> GenerationResponse:
    source_documents = await _read_uploads(files)
    chosen_writer = writer_model or settings.writer_model
    chosen_reviewer = reviewer_model or settings.reviewer_model
    chosen_research = research_model or settings.research_model
    graph = build_graph(settings)
    try:
        result = await graph.ainvoke(
            {
                "prompt": prompt,
                "source_documents": source_documents,
                "style": style,
                "use_research": use_research,
                "writer_model": chosen_writer,
                "reviewer_model": chosen_reviewer,
                "research_model": chosen_research,
            }
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    final_markdown = result.get("final") or result.get("draft")
    if not final_markdown:
        raise HTTPException(status_code=502, detail="The writing graph did not return Markdown.")

    piece = save_piece(
        pieces_dir=settings.pieces_dir,
        markdown=final_markdown,
        prompt=prompt,
        review=result.get("review", ""),
        research_enabled=use_research,
        writer_model=chosen_writer,
        reviewer_model=chosen_reviewer,
        research_model=chosen_research,
    )
    return GenerationResponse(
        piece=piece,
        review=result.get("review", ""),
        research=result.get("research", ""),
    )
