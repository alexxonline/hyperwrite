from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .config import get_settings
from .service import (
    accept_piece_angle_draft,
    apply_piece_followup,
    apply_piece_review,
    ensure_storage,
    generate_piece_angle_draft,
    generate_interview_questions,
    generate_piece,
    get_model_defaults,
    read_source_files,
    suggest_piece_angles,
)
from .storage import delete_piece, list_pieces, read_piece


class CliError(Exception):
    pass


def _model_to_dict(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _model_to_dict(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _print_json(value: Any) -> None:
    print(json.dumps(_jsonable(value), indent=2))


def _prompt_text(args: argparse.Namespace) -> str:
    if args.prompt_file:
        prompt = args.prompt_file.read_text(encoding="utf-8")
    else:
        prompt = args.prompt or ""
    prompt = prompt.strip()
    if not prompt:
        raise CliError("A prompt is required. Pass PROMPT or use --prompt-file.")
    return prompt


def _build_interview_prompt(prompt: str, questions: list[str], answers: list[str]) -> str:
    answered_questions = [
        (question, answers[index].strip() if index < len(answers) else "")
        for index, question in enumerate(questions)
    ]
    answered_questions = [
        (question, answer) for question, answer in answered_questions if answer
    ]
    if not answered_questions:
        return prompt
    return "\n\n".join(
        [
            prompt.strip(),
            "Interview answers:",
            *[
                f"{index + 1}. {question}\nAnswer: {answer}"
                for index, (question, answer) in enumerate(answered_questions)
            ],
        ]
    )


def _read_interview_answers(questions: list[str]) -> list[str]:
    print("Interview questions. Press Enter to skip a question.", file=sys.stderr)
    answers: list[str] = []
    for index, question in enumerate(questions, start=1):
        print(f"\n{index}. {question}", file=sys.stderr)
        print("Answer: ", end="", file=sys.stderr, flush=True)
        raw_answer = sys.stdin.readline()
        if raw_answer == "":
            break
        answers.append(raw_answer.strip())
    if not any(answer.strip() for answer in answers):
        raise CliError("Answer at least one interview question before generating.")
    return answers


def _confirm_delete(slug: str) -> bool:
    answer = input(f'Delete "{slug}"? This cannot be undone. [y/N] ')
    return answer.strip().lower() in {"y", "yes"}


def _confirm_accept_angle() -> bool:
    answer = input("Accept this angle draft and replace the saved piece? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def _select_angle(angles: list[Any]) -> str:
    print("Suggested angles:")
    for index, angle in enumerate(angles, start=1):
        description = f" - {angle.description}" if angle.description else ""
        print(f"{index}. {angle.label}{description}")
    answer = input("Choose 1-3, or c to cancel: ").strip().lower()
    if answer in {"c", "cancel", "q", "quit"}:
        raise CliError("Angle selection cancelled.")
    try:
        selected = int(answer)
    except ValueError as exc:
        raise CliError("Choose 1, 2, or 3.") from exc
    if selected < 1 or selected > len(angles):
        raise CliError("Choose 1, 2, or 3.")
    return angles[selected - 1].label


async def _cmd_generate(args: argparse.Namespace) -> int:
    settings = get_settings()
    ensure_storage(settings)
    prompt = _prompt_text(args)
    try:
        source_file_names, source_documents = read_source_files(args.source)
        if args.interview:
            questions = await generate_interview_questions(
                settings=settings,
                prompt=prompt,
                style=args.style,
                source_documents=source_documents,
                writer_model=args.writer_model,
            )
            answers = _read_interview_answers(questions)
            prompt = _build_interview_prompt(prompt, questions, answers)
        result = await generate_piece(
            settings=settings,
            prompt=prompt,
            style=args.style,
            use_research=args.research,
            use_anti_ai_style=args.anti_ai_style,
            source_file_names=source_file_names,
            source_documents=source_documents,
            writer_model=args.writer_model,
            reviewer_model=args.reviewer_model,
            research_model=args.research_model,
        )
    except ValueError as exc:
        raise CliError(str(exc)) from exc

    if args.json:
        _print_json(result)
        return 0

    print(f"Created: {result.piece.title}")
    print(f"Slug: {result.piece.slug}")
    print(f"Path: {result.piece.path}")
    if args.print_markdown:
        print("\n" + result.piece.markdown.rstrip())
    if args.print_review and result.review.strip():
        print("\n--- Review ---\n")
        print(result.review.rstrip())
    if args.print_research and result.research.strip():
        print("\n--- Research ---\n")
        print(result.research.rstrip())
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    settings = get_settings()
    ensure_storage(settings)
    pieces = list_pieces(settings.pieces_dir)
    if args.search:
        query = args.search.lower()
        pieces = [piece for piece in pieces if query in piece.title.lower()]
    if args.json:
        _print_json(pieces)
        return 0
    if not pieces:
        print("No saved pieces.")
        return 0
    for piece in pieces:
        created = piece.created_at.isoformat()
        flags = []
        if piece.research_enabled:
            flags.append("research")
        if piece.anti_ai_style_enabled:
            flags.append("anti-ai-style")
        suffix = f" ({', '.join(flags)})" if flags else ""
        print(f"{piece.slug}\t{created}\t{piece.title}{suffix}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        piece = read_piece(settings.pieces_dir, args.slug)
    except FileNotFoundError as exc:
        raise CliError(f"Piece not found: {args.slug}") from exc

    if args.json:
        _print_json(piece)
        return 0
    if args.metadata:
        print(f"Title: {piece.title}")
        print(f"Slug: {piece.slug}")
        print(f"Created: {piece.created_at.isoformat()}")
        print(f"Path: {piece.path}")
        print(f"Prompt: {piece.prompt}")
        print(f"Style: {piece.style or '(none)'}")
        print(f"Source files: {', '.join(piece.source_files) if piece.source_files else '(none)'}")
        print(f"Writer model: {piece.writer_model or '(default)'}")
        print(f"Reviewer model: {piece.reviewer_model or '(default)'}")
        print(f"Research model: {piece.research_model or '(default)'}")
        print(f"Research enabled: {piece.research_enabled}")
        print(f"Anti-AI style enabled: {piece.anti_ai_style_enabled}")
        return 0
    if args.review:
        print(piece.review.rstrip())
        return 0
    print(piece.markdown.rstrip())
    return 0


def _cmd_delete(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not args.yes and not _confirm_delete(args.slug):
        print("Delete cancelled.")
        return 0
    try:
        delete_piece(settings.pieces_dir, args.slug)
    except FileNotFoundError as exc:
        raise CliError(f"Piece not found: {args.slug}") from exc
    print(f"Deleted: {args.slug}")
    return 0


async def _cmd_apply_review(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        piece = await apply_piece_review(
            settings=settings,
            slug=args.slug,
            reviewer_model=args.reviewer_model,
            use_anti_ai_style=args.anti_ai_style,
        )
    except FileNotFoundError as exc:
        raise CliError(f"Piece not found: {args.slug}") from exc
    except ValueError as exc:
        raise CliError(str(exc)) from exc

    if args.json:
        _print_json(piece)
        return 0
    print(f"Updated: {piece.title}")
    print(f"Slug: {piece.slug}")
    print(f"Path: {piece.path}")
    if args.print_markdown:
        print("\n" + piece.markdown.rstrip())
    return 0


async def _cmd_follow_up(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        piece = await apply_piece_followup(
            settings=settings,
            slug=args.slug,
            followup_prompt=_prompt_text(args),
            writer_model=args.writer_model,
            reviewer_model=args.reviewer_model,
            use_anti_ai_style=args.anti_ai_style,
        )
    except FileNotFoundError as exc:
        raise CliError(f"Piece not found: {args.slug}") from exc
    except ValueError as exc:
        raise CliError(str(exc)) from exc

    if args.json:
        _print_json(piece)
        return 0
    print(f"Updated: {piece.title}")
    print(f"Slug: {piece.slug}")
    print(f"Path: {piece.path}")
    if args.print_markdown:
        print("\n" + piece.markdown.rstrip())
    return 0


async def _cmd_angles(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        read_piece(settings.pieces_dir, args.slug)
    except FileNotFoundError as exc:
        raise CliError(f"Piece not found: {args.slug}") from exc

    angle = (args.angle or "").strip()
    if not angle:
        angles = await suggest_piece_angles(
            settings=settings,
            slug=args.slug,
            writer_model=args.writer_model,
        )
        if args.json or args.suggest_only:
            if args.json:
                _print_json({"angles": angles})
            else:
                for index, suggestion in enumerate(angles, start=1):
                    description = f" - {suggestion.description}" if suggestion.description else ""
                    print(f"{index}. {suggestion.label}{description}")
            return 0
        angle = _select_angle(angles)

    draft = await generate_piece_angle_draft(
        settings=settings,
        slug=args.slug,
        angle=angle,
        writer_model=args.writer_model,
        use_anti_ai_style=args.anti_ai_style,
    )

    if args.draft_only or (args.json and not args.accept):
        if args.json:
            _print_json(draft)
        else:
            print(draft.markdown.rstrip())
        return 0

    if not args.accept:
        print("\n--- Angle Draft ---\n")
        print(draft.markdown.rstrip())
        print()
        if not _confirm_accept_angle():
            print("Angle rewrite not accepted.")
            return 0

    piece = await accept_piece_angle_draft(
        settings=settings,
        slug=args.slug,
        angle=draft.angle,
        draft_markdown=draft.markdown,
        writer_model=args.writer_model,
        use_anti_ai_style=args.anti_ai_style,
    )

    if args.json:
        _print_json(piece)
        return 0
    print(f"Updated: {piece.title}")
    print(f"Slug: {piece.slug}")
    print(f"Path: {piece.path}")
    if args.print_markdown:
        print("\n" + piece.markdown.rstrip())
    return 0


def _cmd_models(args: argparse.Namespace) -> int:
    defaults = get_model_defaults(get_settings())
    if args.json:
        _print_json(defaults)
        return 0
    print(f"Writer: {defaults.writer_model}")
    print(f"Reviewer: {defaults.reviewer_model}")
    print(f"Research: {defaults.research_model}")
    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    settings = get_settings()
    ensure_storage(settings)
    if args.json:
        _print_json({"status": "ok"})
        return 0
    print("ok")
    return 0


def _cmd_help(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.operation:
        parser.print_help()
        return 0
    subparsers_action = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    operation_parser = subparsers_action.choices.get(args.operation)
    if not operation_parser:
        raise CliError(f"Unknown operation: {args.operation}")
    operation_parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hyperwrite",
        description="Hyperwrite web app companion CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="operation")

    help_parser = subparsers.add_parser("help", help="List operations or show operation usage.")
    help_parser.add_argument("operation", nargs="?", help="Operation to explain.")
    help_parser.set_defaults(handler="help")

    generate_parser = subparsers.add_parser("generate", help="Generate and save a new piece.")
    generate_parser.add_argument("prompt", nargs="?", help="Writing prompt. Use quotes for spaces.")
    generate_parser.add_argument("--prompt-file", type=Path, help="Read the prompt from a UTF-8 file.")
    generate_parser.add_argument(
        "-f",
        "--source",
        type=Path,
        action="append",
        default=[],
        help="Attach a .md, .markdown, or .txt source file. Repeat for multiple files.",
    )
    generate_parser.add_argument("--style", default="", help="Style or constraint notes.")
    generate_parser.add_argument(
        "--research",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use the research agent before drafting.",
    )
    generate_parser.add_argument(
        "--anti-ai-style",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Apply the bundled anti-AI writing style guide.",
    )
    generate_parser.add_argument(
        "--interview",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Ask follow-up questions before generating and append answered context to the prompt.",
    )
    generate_parser.add_argument("--writer-model", help="Override WRITER_MODEL.")
    generate_parser.add_argument("--reviewer-model", help="Override REVIEWER_MODEL.")
    generate_parser.add_argument("--research-model", help="Override RESEARCH_MODEL.")
    generate_parser.add_argument("--json", action="store_true", help="Print the full result as JSON.")
    generate_parser.add_argument("--print-markdown", action="store_true", help="Print generated Markdown.")
    generate_parser.add_argument("--print-review", action="store_true", help="Print reviewer notes.")
    generate_parser.add_argument("--print-research", action="store_true", help="Print research notes.")
    generate_parser.set_defaults(handler=_cmd_generate)

    list_parser = subparsers.add_parser("list", help="List saved pieces.")
    list_parser.add_argument("--search", help="Filter saved pieces by title.")
    list_parser.add_argument("--json", action="store_true", help="Print saved pieces as JSON.")
    list_parser.set_defaults(handler=_cmd_list)

    show_parser = subparsers.add_parser("show", help="Show a saved piece.")
    show_parser.add_argument("slug", help="Saved piece slug.")
    show_group = show_parser.add_mutually_exclusive_group()
    show_group.add_argument("--review", action="store_true", help="Print reviewer notes.")
    show_group.add_argument("--metadata", action="store_true", help="Print metadata.")
    show_group.add_argument("--json", action="store_true", help="Print the whole piece as JSON.")
    show_parser.set_defaults(handler=_cmd_show)

    delete_parser = subparsers.add_parser("delete", help="Delete a saved piece and companion files.")
    delete_parser.add_argument("slug", help="Saved piece slug.")
    delete_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation.")
    delete_parser.set_defaults(handler=_cmd_delete)

    apply_review_parser = subparsers.add_parser(
        "apply-review",
        help="Rewrite a saved piece using its stored reviewer notes.",
    )
    apply_review_parser.add_argument("slug", help="Saved piece slug.")
    apply_review_parser.add_argument("--reviewer-model", help="Override REVIEWER_MODEL.")
    apply_review_parser.add_argument(
        "--anti-ai-style",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override whether the anti-AI style guide is applied.",
    )
    apply_review_parser.add_argument("--json", action="store_true", help="Print the updated piece as JSON.")
    apply_review_parser.add_argument("--print-markdown", action="store_true", help="Print updated Markdown.")
    apply_review_parser.set_defaults(handler=_cmd_apply_review)

    follow_up_parser = subparsers.add_parser(
        "follow-up",
        help="Apply a follow-up revision request to a saved piece.",
    )
    follow_up_parser.add_argument("slug", help="Saved piece slug.")
    follow_up_parser.add_argument("prompt", nargs="?", help="Follow-up request.")
    follow_up_parser.add_argument("--prompt-file", type=Path, help="Read the follow-up request from a file.")
    follow_up_parser.add_argument("--writer-model", help="Override WRITER_MODEL.")
    follow_up_parser.add_argument("--reviewer-model", help="Override REVIEWER_MODEL.")
    follow_up_parser.add_argument(
        "--anti-ai-style",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override whether the anti-AI style guide is applied.",
    )
    follow_up_parser.add_argument("--json", action="store_true", help="Print the updated piece as JSON.")
    follow_up_parser.add_argument("--print-markdown", action="store_true", help="Print updated Markdown.")
    follow_up_parser.set_defaults(handler=_cmd_follow_up)

    angles_parser = subparsers.add_parser(
        "angles",
        help="Suggest alternate angles for a saved piece and optionally rewrite it.",
    )
    angles_parser.add_argument("slug", help="Saved piece slug.")
    angles_parser.add_argument(
        "--angle",
        help="Skip suggestions and generate a draft for this angle.",
    )
    angles_parser.add_argument(
        "--suggest-only",
        action="store_true",
        help="Only print the three suggested angles.",
    )
    angles_parser.add_argument("--writer-model", help="Override WRITER_MODEL.")
    angles_parser.add_argument(
        "--anti-ai-style",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override whether the anti-AI style guide is applied to the draft.",
    )
    angles_parser.add_argument(
        "--draft-only",
        action="store_true",
        help="Generate and print the selected angle draft without saving it.",
    )
    angles_parser.add_argument(
        "--accept",
        action="store_true",
        help="Accept the generated draft without an interactive confirmation.",
    )
    angles_parser.add_argument("--json", action="store_true", help="Print JSON output.")
    angles_parser.add_argument("--print-markdown", action="store_true", help="Print accepted Markdown.")
    angles_parser.set_defaults(handler=_cmd_angles)

    models_parser = subparsers.add_parser("models", help="Show configured model defaults.")
    models_parser.add_argument("--json", action="store_true", help="Print model defaults as JSON.")
    models_parser.set_defaults(handler=_cmd_models)

    health_parser = subparsers.add_parser("health", help="Check local CLI configuration/storage.")
    health_parser.add_argument("--json", action="store_true", help="Print health as JSON.")
    health_parser.set_defaults(handler=_cmd_health)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        if args.handler == "help":
            return _cmd_help(args, parser)
        result = args.handler(args)
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result
    except CliError as exc:
        print(f"hyperwrite: error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"hyperwrite: error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"hyperwrite: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
