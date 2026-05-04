from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from .config import Settings


class WritingState(TypedDict, total=False):
    prompt: str
    source_documents: str
    style: str
    use_research: bool
    research: str
    draft: str
    review: str
    final: str
    writer_model: str
    reviewer_model: str
    research_model: str


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


async def research_node(state: WritingState, settings: Settings) -> WritingState:
    llm = _chat(settings, state["research_model"], temperature=0.2)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a research agent. Use current sources available to you and "
                    "return concise, cited research notes in Markdown. Focus on facts, "
                    "competing viewpoints, key examples, and source URLs."
                )
            ),
            HumanMessage(
                content=(
                    f"Research this writing assignment:\n\n{state['prompt']}\n\n"
                    f"Source material supplied by the user:\n{state.get('source_documents', '')}"
                )
            ),
        ]
    )
    return {"research": str(response.content)}


async def write_node(state: WritingState, settings: Settings) -> WritingState:
    llm = _chat(settings, state["writer_model"], temperature=0.65)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a senior writing agent. Produce a polished written piece in Markdown. "
                    "Start with a single H1 title. Use clear structure, strong prose, and no process notes."
                )
            ),
            HumanMessage(
                content=(
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
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a demanding editorial reviewer. Review the draft for accuracy, "
                    "structure, clarity, completeness, unsupported claims, and fit to prompt. "
                    "Return actionable revision notes in Markdown. Do not rewrite the whole piece."
                )
            ),
            HumanMessage(
                content=(
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
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are the writing agent revising after editorial review. "
                    "Return only the final Markdown piece. It must begin with one H1 title."
                )
            ),
            HumanMessage(
                content=(
                    f"Original prompt:\n{state['prompt']}\n\n"
                    f"Draft:\n{state['draft']}\n\n"
                    f"Reviewer notes:\n{state['review']}\n\n"
                    "Revise the piece so it addresses the review while preserving useful work."
                )
            ),
        ]
    )
    return {"final": str(response.content)}


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
