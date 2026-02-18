"""Interrogation workflow: session state and deterministic draft management."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from spec_eng.dual_spec import DualSpecError, check_specs, compile_spec, load_vocab


class InterrogationError(Exception):
    """Raised when interrogation workflow operations fail."""


@dataclass
class InterrogationQuestion:
    """Single clarifying question in the interrogation loop."""

    id: str
    text: str
    blocking: bool = True


@dataclass
class InterrogationSession:
    """Persistent state for interrogation-driven spec drafting."""

    slug: str
    idea: str
    iteration: int = 0
    approved: bool = False
    answers: dict[str, str] = field(default_factory=dict)
    ir_hash_history: list[str] = field(default_factory=list)
    last_outputs: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "idea": self.idea,
            "iteration": self.iteration,
            "approved": self.approved,
            "answers": dict(sorted(self.answers.items())),
            "ir_hash_history": list(self.ir_hash_history),
            "last_outputs": dict(sorted(self.last_outputs.items())),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InterrogationSession:
        return cls(
            slug=data["slug"],
            idea=data["idea"],
            iteration=int(data.get("iteration", 0)),
            approved=bool(data.get("approved", False)),
            answers=dict(data.get("answers", {})),
            ir_hash_history=list(data.get("ir_hash_history", [])),
            last_outputs=dict(data.get("last_outputs", {})),
        )


def default_slug(idea: str) -> str:
    slug = idea.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug.strip("-") or "interrogation-spec"


def session_path(project_root: Path, slug: str) -> Path:
    return project_root / ".spec-eng" / "interrogation" / f"{slug}.json"


def load_session(project_root: Path, slug: str) -> InterrogationSession | None:
    path = session_path(project_root, slug)
    if not path.exists():
        return None
    return InterrogationSession.from_dict(json.loads(path.read_text()))


def save_session(project_root: Path, session: InterrogationSession) -> Path:
    path = session_path(project_root, session.slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session.to_dict(), indent=2, sort_keys=True) + "\n")
    return path


def parse_answer_flags(answer_flags: tuple[str, ...]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for answer in answer_flags:
        if "=" not in answer:
            raise InterrogationError(f"Invalid --answer '{answer}', expected key=value")
        key, value = answer.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def build_questions(session: InterrogationSession) -> list[InterrogationQuestion]:
    questions: list[InterrogationQuestion] = []
    if "success_criteria" not in session.answers:
        questions.append(InterrogationQuestion(
            id="success_criteria",
            text="What observable behavior proves this idea is successful?",
        ))
    if "failure_case" not in session.answers:
        questions.append(InterrogationQuestion(
            id="failure_case",
            text="What failure or invalid input behavior must be specified?",
        ))
    if "constraints" not in session.answers:
        questions.append(InterrogationQuestion(
            id="constraints",
            text="What constraints or limits must be explicit in acceptance behavior?",
        ))
    return questions


def render_draft_gwt(session: InterrogationSession) -> str:
    """Render a deterministic draft GWT file from session state."""
    title = session.idea.strip().rstrip(".")
    success = session.answers.get("success_criteria")
    failure = session.answers.get("failure_case")
    constraints = session.answers.get("constraints")

    lines = [
        ";===============================================================",
        f"; Interrogation draft for: {title}.",
        ";===============================================================",
        f"GIVEN there is no acceptance spec describing {title}.",
        "",
        f"WHEN the user starts the ATDD workflow for \"{title}\".",
        "",
        f"THEN a DAL spec file exists at \"specs/{session.slug}.dal\".",
        f"THEN a GWT spec file exists at \"specs/{session.slug}.txt\".",
    ]

    if success:
        lines.append(f"THEN the regenerated GWT spec includes a scenario describing {success}.")
    if failure:
        lines.append(f"THEN the regenerated GWT spec includes a scenario describing {failure}.")
    if constraints:
        lines.append(f"THEN the regenerated GWT spec includes a scenario describing {constraints}.")

    return "\n".join(lines) + "\n"


def interrogate_iteration(
    project_root: Path,
    idea: str,
    slug: str | None,
    answers: dict[str, str],
    approve: bool,
) -> tuple[InterrogationSession, list[InterrogationQuestion]]:
    """Run one deterministic interrogation iteration."""
    resolved_slug = slug or default_slug(idea)
    session = load_session(project_root, resolved_slug)
    if session is None:
        session = InterrogationSession(slug=resolved_slug, idea=idea.strip())

    if idea.strip() and session.idea != idea.strip() and session.iteration > 0:
        raise InterrogationError(
            f"Session '{resolved_slug}' already exists for a different idea"
        )

    session.answers.update({k: v for k, v in answers.items() if v})
    session.iteration += 1

    specs_dir = project_root / "specs"
    specs_dir.mkdir(exist_ok=True)
    gwt_path = specs_dir / f"{session.slug}.txt"
    gwt_path.write_text(render_draft_gwt(session))

    vocab_path = specs_dir / "vocab.yaml"
    if not vocab_path.exists():
        raise InterrogationError(f"Missing vocabulary file: {vocab_path}")

    try:
        vocab = load_vocab(vocab_path)
        outputs = compile_spec(gwt_path, vocab, project_root=project_root)
    except DualSpecError as exc:
        raise InterrogationError(str(exc)) from exc

    violations = check_specs(gwt_path, vocab)
    if violations:
        first = violations[0]
        raise InterrogationError(
            f"spec-check violation at {first.file}:{first.line}:{first.column}: {first.message}"
        )

    ir_path = outputs["ir"]
    ir_hash = sha256(ir_path.read_bytes()).hexdigest()
    session.ir_hash_history.append(ir_hash)
    session.last_outputs = {k: str(v) for k, v in outputs.items()}

    questions = build_questions(session)

    stable = len(session.ir_hash_history) >= 2 and session.ir_hash_history[-1] == session.ir_hash_history[-2]
    if approve:
        if questions:
            raise InterrogationError("Cannot approve: unresolved blocking questions remain")
        if not stable:
            raise InterrogationError("Cannot approve: IR is not yet stable across iterations")
        session.approved = True

    save_session(project_root, session)
    return session, questions
