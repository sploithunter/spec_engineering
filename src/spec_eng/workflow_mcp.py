"""Standalone MCP server for dual-spec workflow operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from spec_eng.dual_spec import check_specs, compile_spec, load_vocab
from spec_eng.interrogation import interrogate_iteration, parse_answer_flags

mcp = FastMCP("spec-eng-workflow")


def _load_vocab_for_root(project_root: Path):
    vocab_path = project_root / "specs" / "vocab.yaml"
    if not vocab_path.exists():
        raise FileNotFoundError(f"Missing vocabulary file: {vocab_path}")
    return load_vocab(vocab_path)


def _spec_compile(input_path: str, project_root: str = ".") -> dict[str, Any]:
    root = Path(project_root)
    source = Path(input_path)
    if not source.is_absolute():
        source = root / source

    vocab = _load_vocab_for_root(root)
    outputs = compile_spec(source, vocab, project_root=root)
    return {
        "ok": True,
        "outputs": {k: str(v) for k, v in sorted(outputs.items())},
    }


def _spec_check(input_path: str, project_root: str = ".") -> dict[str, Any]:
    root = Path(project_root)
    target = Path(input_path)
    if not target.is_absolute():
        target = root / target

    vocab = _load_vocab_for_root(root)
    violations = check_specs(target, vocab)
    return {
        "ok": len(violations) == 0,
        "count": len(violations),
        "violations": [
            {
                "file": v.file,
                "line": v.line,
                "column": v.column,
                "kind": v.kind,
                "matched": v.matched,
                "message": v.message,
                "suggestion": v.suggestion,
            }
            for v in violations
        ],
    }


def _interrogate(
    idea: str,
    project_root: str = ".",
    slug: str | None = None,
    answers: list[str] | None = None,
    approve: bool = False,
) -> dict[str, Any]:
    root = Path(project_root)
    parsed_answers = parse_answer_flags(tuple(answers or []))
    session, questions = interrogate_iteration(
        project_root=root,
        idea=idea,
        slug=slug,
        answers=parsed_answers,
        approve=approve,
    )
    return {
        "ok": True,
        "session": session.to_dict(),
        "questions": [
            {"id": q.id, "text": q.text, "blocking": q.blocking}
            for q in questions
        ],
    }


@mcp.tool()
def spec_compile(input_path: str, project_root: str = ".") -> dict[str, Any]:
    """Compile a GWT/DAL file and emit synchronized DAL/GWT/IR artifacts."""
    return _spec_compile(input_path=input_path, project_root=project_root)


@mcp.tool()
def spec_check(input_path: str, project_root: str = ".") -> dict[str, Any]:
    """Run vocab lint checks for implementation leakage on a file or directory."""
    return _spec_check(input_path=input_path, project_root=project_root)


@mcp.tool()
def interrogate(
    idea: str,
    project_root: str = ".",
    slug: str | None = None,
    answers: list[str] | None = None,
    approve: bool = False,
) -> dict[str, Any]:
    """Run one interrogation iteration and compile synchronized artifacts."""
    return _interrogate(
        idea=idea,
        project_root=project_root,
        slug=slug,
        answers=answers,
        approve=approve,
    )
