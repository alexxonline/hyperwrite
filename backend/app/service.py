from __future__ import annotations

from pathlib import Path

from .config import Settings
from .graph import apply_followup_revision, apply_review_rewrite, build_graph
from .models import GenerationResponse, ModelDefaults, Piece
from .storage import read_piece, save_piece, update_piece_markdown


SUPPORTED_SOURCE_SUFFIXES = {".md", ".markdown", ".txt"}


def ensure_storage(settings: Settings) -> None:
    settings.pieces_dir.mkdir(parents=True, exist_ok=True)


def get_model_defaults(settings: Settings) -> ModelDefaults:
    return ModelDefaults(
        writer_model=settings.writer_model,
        reviewer_model=settings.reviewer_model,
        research_model=settings.research_model,
    )


def read_source_files(paths: list[Path]) -> tuple[list[str], str]:
    chunks: list[str] = []
    source_file_names: list[str] = []
    for path in paths:
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SOURCE_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_SOURCE_SUFFIXES))
            raise ValueError(f"{path} is not supported. Use one of: {supported}.")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path} must be UTF-8 encoded.") from exc
        source_file_names.append(path.name)
        chunks.append(f"## File: {path.name}\n\n{text.strip()}")
    return source_file_names, "\n\n".join(chunks)


async def generate_piece(
    *,
    settings: Settings,
    prompt: str,
    style: str = "",
    use_research: bool = False,
    use_anti_ai_style: bool = False,
    source_file_names: list[str] | None = None,
    source_documents: str = "",
    writer_model: str | None = None,
    reviewer_model: str | None = None,
    research_model: str | None = None,
) -> GenerationResponse:
    chosen_writer = writer_model or settings.writer_model
    chosen_reviewer = reviewer_model or settings.reviewer_model
    chosen_research = research_model or settings.research_model
    graph = build_graph(settings)
    result = await graph.ainvoke(
        {
            "prompt": prompt,
            "source_documents": source_documents,
            "style": style,
            "use_research": use_research,
            "use_anti_ai_style": use_anti_ai_style,
            "writer_model": chosen_writer,
            "reviewer_model": chosen_reviewer,
            "research_model": chosen_research,
        }
    )

    final_markdown = result.get("final") or result.get("draft")
    if not final_markdown:
        raise RuntimeError("The writing graph did not return Markdown.")

    piece = save_piece(
        pieces_dir=settings.pieces_dir,
        markdown=final_markdown,
        prompt=prompt,
        style=style,
        source_files=source_file_names or [],
        review=result.get("review", ""),
        research_enabled=use_research,
        anti_ai_style_enabled=use_anti_ai_style,
        writer_model=chosen_writer,
        reviewer_model=chosen_reviewer,
        research_model=chosen_research,
    )
    return GenerationResponse(
        piece=piece,
        review=result.get("review", ""),
        research=result.get("research", ""),
    )


async def apply_piece_review(
    *,
    settings: Settings,
    slug: str,
    reviewer_model: str | None = None,
    use_anti_ai_style: bool | None = None,
) -> Piece:
    piece = read_piece(settings.pieces_dir, slug)
    if not piece.review.strip():
        raise ValueError("This piece does not have review notes to apply.")

    chosen_reviewer = reviewer_model or settings.reviewer_model
    chosen_anti_ai_style = (
        piece.anti_ai_style_enabled if use_anti_ai_style is None else use_anti_ai_style
    )
    rewritten = await apply_review_rewrite(
        settings=settings,
        article_markdown=piece.markdown,
        review=piece.review,
        prompt=piece.prompt,
        reviewer_model=chosen_reviewer,
        use_anti_ai_style=chosen_anti_ai_style,
    )

    return update_piece_markdown(
        pieces_dir=settings.pieces_dir,
        slug=slug,
        markdown=rewritten,
        reviewer_model=chosen_reviewer,
        anti_ai_style_enabled=chosen_anti_ai_style,
    )


async def apply_piece_followup(
    *,
    settings: Settings,
    slug: str,
    followup_prompt: str,
    writer_model: str | None = None,
    reviewer_model: str | None = None,
    use_anti_ai_style: bool | None = None,
) -> Piece:
    if not followup_prompt.strip():
        raise ValueError("Follow-up prompt is required.")

    piece = read_piece(settings.pieces_dir, slug)
    chosen_writer = writer_model or settings.writer_model
    chosen_reviewer = reviewer_model or settings.reviewer_model
    chosen_anti_ai_style = (
        piece.anti_ai_style_enabled if use_anti_ai_style is None else use_anti_ai_style
    )
    final_markdown, review = await apply_followup_revision(
        settings=settings,
        article_markdown=piece.markdown,
        original_prompt=piece.prompt,
        followup_prompt=followup_prompt.strip(),
        writer_model=chosen_writer,
        reviewer_model=chosen_reviewer,
        use_anti_ai_style=chosen_anti_ai_style,
    )

    return update_piece_markdown(
        pieces_dir=settings.pieces_dir,
        slug=slug,
        markdown=final_markdown,
        writer_model=chosen_writer,
        reviewer_model=chosen_reviewer,
        review=review,
        followup_prompt=followup_prompt.strip(),
        anti_ai_style_enabled=chosen_anti_ai_style,
    )
