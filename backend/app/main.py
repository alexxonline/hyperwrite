from __future__ import annotations

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .models import GenerationResponse, InterviewQuestionsResponse, ModelDefaults, Piece, PieceSummary
from .service import (
    SUPPORTED_SOURCE_SUFFIXES,
    apply_piece_followup as apply_piece_followup_service,
    apply_piece_review as apply_piece_review_service,
    ensure_storage,
    generate_piece,
    generate_interview_questions,
    get_model_defaults as get_model_defaults_service,
)
from .storage import delete_piece, list_pieces, read_piece


app = FastAPI(title="Hyperwrite API")


@app.on_event("startup")
async def _ensure_storage() -> None:
    ensure_storage(get_settings())


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
        filename = uploaded.filename or ""
        suffix = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
        if suffix not in SUPPORTED_SOURCE_SUFFIXES:
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
    return get_model_defaults_service(settings)


@app.get("/api/pieces", response_model=list[PieceSummary])
async def get_pieces(settings: Settings = Depends(get_settings)) -> list[PieceSummary]:
    return list_pieces(settings.pieces_dir)


@app.get("/api/pieces/{slug}", response_model=Piece)
async def get_piece(slug: str, settings: Settings = Depends(get_settings)) -> Piece:
    try:
        return read_piece(settings.pieces_dir, slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Piece not found.") from exc


@app.delete("/api/pieces/{slug}", status_code=204)
async def remove_piece(slug: str, settings: Settings = Depends(get_settings)) -> None:
    try:
        delete_piece(settings.pieces_dir, slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Piece not found.") from exc


@app.post("/api/pieces/{slug}/apply-review", response_model=Piece)
async def apply_piece_review(
    slug: str,
    reviewer_model: str | None = Form(None),
    use_anti_ai_style: bool | None = Form(None),
    settings: Settings = Depends(get_settings),
) -> Piece:
    try:
        piece = read_piece(settings.pieces_dir, slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Piece not found.") from exc
    if not piece.review.strip():
        raise HTTPException(status_code=400, detail="This piece does not have review notes to apply.")

    try:
        return await apply_piece_review_service(
            settings=settings,
            slug=slug,
            reviewer_model=reviewer_model,
            use_anti_ai_style=use_anti_ai_style,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pieces/{slug}/follow-up", response_model=Piece)
async def apply_piece_followup(
    slug: str,
    followup_prompt: str = Form(...),
    writer_model: str | None = Form(None),
    reviewer_model: str | None = Form(None),
    use_anti_ai_style: bool | None = Form(None),
    settings: Settings = Depends(get_settings),
) -> Piece:
    if not followup_prompt.strip():
        raise HTTPException(status_code=400, detail="Follow-up prompt is required.")
    try:
        read_piece(settings.pieces_dir, slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Piece not found.") from exc

    try:
        return await apply_piece_followup_service(
            settings=settings,
            slug=slug,
            followup_prompt=followup_prompt.strip(),
            writer_model=writer_model,
            reviewer_model=reviewer_model,
            use_anti_ai_style=use_anti_ai_style,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pieces", response_model=GenerationResponse)
async def create_piece(
    prompt: str = Form(...),
    use_research: bool = Form(False),
    use_anti_ai_style: bool = Form(False),
    style: str = Form(""),
    writer_model: str | None = Form(None),
    reviewer_model: str | None = Form(None),
    research_model: str | None = Form(None),
    files: list[UploadFile] | None = File(None),
    settings: Settings = Depends(get_settings),
) -> GenerationResponse:
    source_file_names = [uploaded.filename or "untitled" for uploaded in files or []]
    source_documents = await _read_uploads(files)
    try:
        return await generate_piece(
            settings=settings,
            prompt=prompt,
            style=style,
            source_file_names=source_file_names,
            source_documents=source_documents,
            use_research=use_research,
            use_anti_ai_style=use_anti_ai_style,
            writer_model=writer_model,
            reviewer_model=reviewer_model,
            research_model=research_model,
        )
    except RuntimeError as exc:
        status_code = 502 if str(exc) == "The writing graph did not return Markdown." else 500
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.post("/api/interview-questions", response_model=InterviewQuestionsResponse)
async def create_interview_questions(
    prompt: str = Form(...),
    style: str = Form(""),
    writer_model: str | None = Form(None),
    files: list[UploadFile] | None = File(None),
    settings: Settings = Depends(get_settings),
) -> InterviewQuestionsResponse:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required.")
    source_documents = await _read_uploads(files)
    try:
        questions = await generate_interview_questions(
            settings=settings,
            prompt=prompt.strip(),
            style=style,
            source_documents=source_documents,
            writer_model=writer_model,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return InterviewQuestionsResponse(questions=questions)
