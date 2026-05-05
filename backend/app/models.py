from datetime import datetime

from pydantic import BaseModel, Field


class PieceSummary(BaseModel):
    slug: str
    title: str
    created_at: datetime
    path: str
    research_enabled: bool = False
    anti_ai_style_enabled: bool = False


class Piece(PieceSummary):
    markdown: str
    review: str = ""
    prompt: str = ""
    style: str = ""
    source_files: list[str] = Field(default_factory=list)
    writer_model: str = ""
    reviewer_model: str = ""
    research_model: str = ""


class GenerationResponse(BaseModel):
    piece: Piece
    review: str
    research: str = ""


class ModelDefaults(BaseModel):
    writer_model: str
    reviewer_model: str
    research_model: str


class GenerationOptions(BaseModel):
    prompt: str = Field(min_length=1)
    use_research: bool = False
    use_anti_ai_style: bool = False
    style: str = ""
    writer_model: str | None = None
    reviewer_model: str | None = None
    research_model: str | None = None
