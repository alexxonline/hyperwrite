from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from .models import Piece, PieceSummary


SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = SLUG_PATTERN.sub("-", value.lower()).strip("-")
    return slug[:80] or "untitled"


def extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return "Untitled piece"


def _quote_frontmatter(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def build_markdown_document(
    *,
    markdown: str,
    prompt: str,
    review: str,
    research_enabled: bool,
    writer_model: str,
    reviewer_model: str,
    research_model: str,
    created_at: datetime | None = None,
) -> tuple[str, str, datetime]:
    created = created_at or datetime.now(UTC)
    title = extract_title(markdown)
    frontmatter = [
        "---",
        f"title: {_quote_frontmatter(title)}",
        f"created_at: {created.isoformat()}",
        f"research_enabled: {str(research_enabled).lower()}",
        f"writer_model: {_quote_frontmatter(writer_model)}",
        f"reviewer_model: {_quote_frontmatter(reviewer_model)}",
        f"research_model: {_quote_frontmatter(research_model)}",
        f"prompt: {_quote_frontmatter(prompt)}",
        "review: |-",
    ]
    frontmatter.extend(f"  {line}" for line in review.splitlines() or [""])
    frontmatter.append("---")
    return title, "\n".join(frontmatter) + "\n\n" + markdown.strip() + "\n", created


def save_piece(
    *,
    pieces_dir: Path,
    markdown: str,
    prompt: str,
    review: str,
    research_enabled: bool,
    writer_model: str,
    reviewer_model: str,
    research_model: str,
) -> Piece:
    pieces_dir.mkdir(parents=True, exist_ok=True)
    title, document, created_at = build_markdown_document(
        markdown=markdown,
        prompt=prompt,
        review=review,
        research_enabled=research_enabled,
        writer_model=writer_model,
        reviewer_model=reviewer_model,
        research_model=research_model,
    )
    base_slug = slugify(title)
    stamp = created_at.strftime("%Y%m%d%H%M%S")
    slug = f"{base_slug}-{stamp}"
    path = pieces_dir / f"{slug}.md"
    path.write_text(document, encoding="utf-8")
    return Piece(
        slug=slug,
        title=title,
        created_at=created_at,
        path=str(path),
        markdown=document,
        review=review,
        prompt=prompt,
        research_enabled=research_enabled,
    )


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    if not markdown.startswith("---\n"):
        return {}, markdown
    try:
        _, frontmatter, body = markdown.split("---", 2)
    except ValueError:
        return {}, markdown

    metadata: dict[str, str] = {}
    current_key: str | None = None
    block_lines: list[str] = []
    for raw_line in frontmatter.strip("\n").splitlines():
        if raw_line.startswith("  ") and current_key:
            block_lines.append(raw_line[2:])
            continue
        if current_key:
            metadata[current_key] = "\n".join(block_lines).strip()
            current_key = None
            block_lines = []
        if ": |-" in raw_line:
            current_key = raw_line.split(":", 1)[0].strip()
            block_lines = []
            continue
        if ":" in raw_line:
            key, value = raw_line.split(":", 1)
            metadata[key.strip()] = value.strip().strip('"')
    if current_key:
        metadata[current_key] = "\n".join(block_lines).strip()
    return metadata, body.strip()


def list_pieces(pieces_dir: Path) -> list[PieceSummary]:
    if not pieces_dir.exists():
        return []
    summaries: list[PieceSummary] = []
    for path in sorted(pieces_dir.glob("*.md"), reverse=True):
        raw = path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(raw)
        created_raw = metadata.get("created_at", datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat())
        created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        summaries.append(
            PieceSummary(
                slug=path.stem,
                title=metadata.get("title") or extract_title(body),
                created_at=created,
                path=str(path),
                research_enabled=metadata.get("research_enabled") == "true",
            )
        )
    return summaries


def read_piece(pieces_dir: Path, slug: str) -> Piece:
    path = pieces_dir / f"{slug}.md"
    raw = path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(raw)
    created_raw = metadata.get("created_at", datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat())
    created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
    return Piece(
        slug=path.stem,
        title=metadata.get("title") or extract_title(body),
        created_at=created,
        path=str(path),
        markdown=raw,
        review=metadata.get("review", ""),
        prompt=metadata.get("prompt", ""),
        research_enabled=metadata.get("research_enabled") == "true",
    )
