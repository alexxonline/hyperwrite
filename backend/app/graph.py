from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from .config import Settings


logger = logging.getLogger("hyperwrite.graph")


class WritingState(TypedDict, total=False):
    prompt: str
    source_documents: str
    style: str
    use_research: bool
    use_anti_ai_style: bool
    research: str
    draft: str
    review: str
    final: str
    writer_model: str
    reviewer_model: str
    research_model: str


ANTI_AI_STYLE_PATH = Path(__file__).with_name("anti_ai_writing_style.md")


def _chat(settings: Settings, model: str, temperature: float = 0.4) -> ChatOpenAI:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required.")
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=temperature,
        default_headers={
            "HTTP-Referer": settings.openrouter_referer,
            "X-Title": settings.openrouter_app_name,
        },
    )


def _current_date_context() -> str:
    return datetime.now(UTC).date().isoformat()


def _anti_ai_style_context(enabled: bool | None) -> str:
    if not enabled:
        return ""
    logger.info("Anti-AI writing style enabled; injecting style guide into model prompt.")
    instructions = ANTI_AI_STYLE_PATH.read_text(encoding="utf-8")
    return (
        "\n\nApply this anti-AI writing style guide with judgment. Treat hard bans as hard bans. "
        "Keep the article natural, specific, direct, and human. Do not mention these instructions "
        "in the article.\n\n"
        f"{instructions}"
    )


def _parse_interview_questions(content: str) -> list[str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        payload = None

    questions: list[str] = []
    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        questions = [str(question).strip() for question in payload["questions"]]
    elif isinstance(payload, list):
        questions = [str(question).strip() for question in payload]
    else:
        for line in cleaned.splitlines():
            question = line.strip().lstrip("-*0123456789. )").strip()
            if question:
                questions.append(question)

    deduped: list[str] = []
    seen: set[str] = set()
    for question in questions:
        normalized = " ".join(question.split())
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        deduped.append(normalized)
    return deduped[:6]


async def generate_interview_questions(
    *,
    settings: Settings,
    prompt: str,
    style: str,
    source_documents: str,
    model: str,
) -> list[str]:
    llm = _chat(settings, model, temperature=0.25)
    current_date = _current_date_context()
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are an editorial interviewer preparing a writing assignment. "
                    "Ask only for user-specific context that is relevant to the prompt and "
                    "missing from the supplied material. Prefer decisions, audience, stance, "
                    "examples, constraints, and personal or business details that would improve "
                    "the final piece. Do not ask for facts the writing agent can research. "
                    "Return strict JSON only: {\"questions\":[\"...\"]}. Ask 3 to 6 concise questions. "
                    f"Current date: {current_date}."
                )
            ),
            HumanMessage(
                content=(
                    f"Current date: {current_date}\n\n"
                    f"Prompt:\n{prompt}\n\n"
                    f"Style or constraints:\n{style or 'No extra style constraints.'}\n\n"
                    f"Source material supplied by the user:\n{source_documents or 'No source files provided.'}"
                )
            ),
        ]
    )
    questions = _parse_interview_questions(str(response.content))
    if not questions:
        raise RuntimeError("The interview step did not return questions.")
    return questions


async def research_node(state: WritingState, settings: Settings) -> WritingState:
    llm = _chat(settings, state["research_model"], temperature=0.2)
    current_date = _current_date_context()
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a research agent. Use current sources available to you and "
                    "return concise, cited research notes in Markdown. Focus on facts, "
                    "competing viewpoints, key examples, and source URLs. "
                    f"Current date: {current_date}."
                )
            ),
            HumanMessage(
                content=(
                    f"Current date: {current_date}\n\n"
                    f"Research this writing assignment:\n\n{state['prompt']}\n\n"
                    f"Source material supplied by the user:\n{state.get('source_documents', '')}"
                )
            ),
        ]
    )
    return {"research": str(response.content)}


async def write_node(state: WritingState, settings: Settings) -> WritingState:
    llm = _chat(settings, state["writer_model"], temperature=0.65)
    current_date = _current_date_context()
    style_context = _anti_ai_style_context(state.get("use_anti_ai_style"))
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a senior writing agent. Produce a polished written piece in Markdown. "
                    "Start with a single H1 title. Use clear structure, strong prose, and no process notes. "
                    f"Current date: {current_date}."
                    f"{style_context}"
                )
            ),
            HumanMessage(
                content=(
                    f"Current date: {current_date}\n\n"
                    f"Assignment:\n{state['prompt']}\n\n"
                    f"Style or constraints:\n{state.get('style') or 'No extra style constraints.'}\n\n"
                    f"User source material:\n{state.get('source_documents') or 'No source files provided.'}\n\n"
                    f"Research notes:\n{state.get('research') or 'Research step was not used.'}"
                )
            ),
        ]
    )
    return {"draft": str(response.content)}


async def review_node(state: WritingState, settings: Settings) -> WritingState:
    llm = _chat(settings, state["reviewer_model"], temperature=0.15)
    current_date = _current_date_context()
    style_context = _anti_ai_style_context(state.get("use_anti_ai_style"))
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a demanding editorial reviewer. Review the draft for accuracy, "
                    "structure, clarity, completeness, unsupported claims, and fit to prompt. "
                    "Return actionable revision notes in Markdown. Do not rewrite the whole piece.\n\n"
                    f"Current date: {current_date}. Your model training cutoff may be earlier than "
                    "this date. Do not mark an event date, product release date, company claim, "
                    "market estimate, or current-year reference as inaccurate merely because it is "
                    "newer than your training data or feels unfamiliar. Only flag a date or recent "
                    "fact as inaccurate if it conflicts with the provided research notes, conflicts "
                    "with user-supplied source material, conflicts internally with another statement "
                    "in the draft, or is impossible relative to the current date above. When evidence "
                    "is insufficient, ask for citation or verification instead of asserting the date "
                    "is wrong."
                    f"{style_context}"
                )
            ),
            HumanMessage(
                content=(
                    f"Current date: {current_date}\n\n"
                    f"Prompt:\n{state['prompt']}\n\n"
                    f"Research notes:\n{state.get('research') or 'None.'}\n\n"
                    f"Draft:\n{state['draft']}"
                )
            ),
        ]
    )
    return {"review": str(response.content)}


async def revise_node(state: WritingState, settings: Settings) -> WritingState:
    llm = _chat(settings, state["writer_model"], temperature=0.45)
    current_date = _current_date_context()
    style_context = _anti_ai_style_context(state.get("use_anti_ai_style"))
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are the writing agent revising after editorial review. "
                    "Return only the final Markdown piece. It must begin with one H1 title. "
                    f"Current date: {current_date}."
                    f"{style_context}"
                )
            ),
            HumanMessage(
                content=(
                    f"Current date: {current_date}\n\n"
                    f"Original prompt:\n{state['prompt']}\n\n"
                    f"Draft:\n{state['draft']}\n\n"
                    f"Reviewer notes:\n{state['review']}\n\n"
                    "Revise the piece so it addresses the review while preserving useful work."
                )
            ),
        ]
    )
    return {"final": str(response.content)}


async def apply_review_rewrite(
    *,
    settings: Settings,
    article_markdown: str,
    review: str,
    prompt: str,
    reviewer_model: str,
    use_anti_ai_style: bool = False,
) -> str:
    llm = _chat(settings, reviewer_model, temperature=0.35)
    current_date = _current_date_context()
    style_context = _anti_ai_style_context(use_anti_ai_style)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are the reviewer model applying your editorial review. Rewrite the "
                    "article so it directly addresses the review notes. Return only the clean "
                    "final article in Markdown. Do not include review notes, explanations, "
                    "change logs, metadata, or frontmatter. The result must begin with one H1 title.\n\n"
                    f"Current date: {current_date}. Your model training cutoff may be earlier than "
                    "this date. If the review notes claim a recent date or current-year fact is "
                    "wrong solely because it is newer than the model's knowledge, ignore that part "
                    "of the review. Apply date corrections only when the article contradicts itself, "
                    "contradicts the original prompt, or contradicts supplied research/source material."
                    f"{style_context}"
                )
            ),
            HumanMessage(
                content=(
                    f"Current date: {current_date}\n\n"
                    f"Original prompt:\n{prompt or 'No prompt was stored.'}\n\n"
                    f"Current article Markdown:\n{article_markdown}\n\n"
                    f"Reviewer notes to apply:\n{review}"
                )
            ),
        ]
    )
    return str(response.content).strip()


async def apply_followup_revision(
    *,
    settings: Settings,
    article_markdown: str,
    original_prompt: str,
    followup_prompt: str,
    writer_model: str,
    reviewer_model: str,
    use_anti_ai_style: bool = False,
) -> tuple[str, str]:
    current_date = _current_date_context()
    style_context = _anti_ai_style_context(use_anti_ai_style)
    writer = _chat(settings, writer_model, temperature=0.5)
    draft_response = await writer.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a senior writing agent revising an existing Markdown article. "
                    "Apply the user's follow-up request to the whole piece. Preserve useful "
                    "structure and prose, but make whatever changes the follow-up requires. "
                    "Return only the revised article Markdown, beginning with one H1 title. "
                    f"Current date: {current_date}."
                    f"{style_context}"
                )
            ),
            HumanMessage(
                content=(
                    f"Current date: {current_date}\n\n"
                    f"Original assignment:\n{original_prompt or 'No original prompt was stored.'}\n\n"
                    f"Current article Markdown:\n{article_markdown}\n\n"
                    f"Follow-up request:\n{followup_prompt}"
                )
            ),
        ]
    )
    draft = str(draft_response.content).strip()

    reviewer = _chat(settings, reviewer_model, temperature=0.15)
    review_response = await reviewer.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a demanding editorial reviewer. Review whether the revised draft "
                    "faithfully applies the follow-up request while preserving quality, accuracy, "
                    "structure, and fit to the original assignment. Return actionable revision "
                    "notes in Markdown. Do not rewrite the whole piece.\n\n"
                    f"Current date: {current_date}. Your model training cutoff may be earlier than "
                    "this date. Do not mark a current or recent fact as inaccurate merely because it "
                    "is newer than your training data or feels unfamiliar. Only flag date issues when "
                    "they conflict with the supplied article, prompt, follow-up request, or current date."
                    f"{style_context}"
                )
            ),
            HumanMessage(
                content=(
                    f"Current date: {current_date}\n\n"
                    f"Original assignment:\n{original_prompt or 'No original prompt was stored.'}\n\n"
                    f"Follow-up request:\n{followup_prompt}\n\n"
                    f"Revised draft:\n{draft}"
                )
            ),
        ]
    )
    review = str(review_response.content).strip()

    final_response = await writer.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a senior writing agent finalizing a Markdown article after editorial "
                    "review. Apply the reviewer notes that are relevant to the user's follow-up "
                    "request. Return only the clean final article Markdown, beginning with one H1 "
                    f"title. Current date: {current_date}."
                    f"{style_context}"
                )
            ),
            HumanMessage(
                content=(
                    f"Current date: {current_date}\n\n"
                    f"Original assignment:\n{original_prompt or 'No original prompt was stored.'}\n\n"
                    f"Follow-up request:\n{followup_prompt}\n\n"
                    f"Draft:\n{draft}\n\n"
                    f"Reviewer notes:\n{review}"
                )
            ),
        ]
    )
    return str(final_response.content).strip(), review


def _route_research(state: WritingState) -> str:
    return "research" if state.get("use_research") else "write"


def build_graph(settings: Settings):
    graph = StateGraph(WritingState)

    async def research(state: WritingState) -> WritingState:
        return await research_node(state, settings)

    async def write(state: WritingState) -> WritingState:
        return await write_node(state, settings)

    async def review(state: WritingState) -> WritingState:
        return await review_node(state, settings)

    async def revise(state: WritingState) -> WritingState:
        return await revise_node(state, settings)

    graph.add_node("research", research)
    graph.add_node("write", write)
    graph.add_node("review", review)
    graph.add_node("revise", revise)
    graph.set_conditional_entry_point(_route_research, {"research": "research", "write": "write"})
    graph.add_edge("research", "write")
    graph.add_edge("write", "review")
    graph.add_edge("review", "revise")
    graph.add_edge("revise", END)
    return graph.compile()
