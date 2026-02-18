"""Unit tests for interrogation workflow state and drafting."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_eng.interrogation import (
    InterrogationError,
    InterrogationSession,
    build_questions,
    detect_vague_terms,
    default_slug,
    interrogate_iteration,
    is_ir_stable,
    load_session,
    parse_answer_flags,
    render_draft_gwt,
    save_session,
)


def test_default_slug_normalizes_text() -> None:
    assert default_slug("User Login Flow!") == "user-login-flow"


def test_parse_answer_flags_valid() -> None:
    parsed = parse_answer_flags(("success_criteria=user logs in", "constraints=rate limited"))
    assert parsed["success_criteria"] == "user logs in"
    assert parsed["constraints"] == "rate limited"


def test_parse_answer_flags_invalid() -> None:
    with pytest.raises(InterrogationError, match="expected key=value"):
        parse_answer_flags(("bad-flag",))


def test_session_save_and_load_roundtrip(tmp_path: Path) -> None:
    session = InterrogationSession(slug="idea", idea="Idea")
    session.iteration = 2
    session.answers["success_criteria"] = "works"

    save_session(tmp_path, session)
    loaded = load_session(tmp_path, "idea")

    assert loaded is not None
    assert loaded.slug == "idea"
    assert loaded.iteration == 2
    assert loaded.answers["success_criteria"] == "works"


def test_build_questions_tracks_missing_answers() -> None:
    session = InterrogationSession(slug="idea", idea="Idea")
    q = build_questions(session)
    assert {item.id for item in q} == {"success_criteria", "failure_case", "constraints"}

    session.answers.update({"success_criteria": "ok", "failure_case": "bad", "constraints": "limit"})
    assert build_questions(session) == []


def test_build_questions_flags_vague_language_non_blocking() -> None:
    session = InterrogationSession(slug="idea", idea="Need a fast and intuitive flow")
    session.answers.update({"success_criteria": "works", "failure_case": "fails safely", "constraints": "rate limit 5"})
    questions = build_questions(session)
    assert len(questions) == 1
    assert questions[0].id == "replace_vague_terms"
    assert not questions[0].blocking


def test_detect_vague_terms() -> None:
    hits = detect_vague_terms("fast response", "robust behavior", "exactly 3 retries")
    assert hits == {"fast", "robust"}


def test_render_draft_gwt_includes_answers() -> None:
    session = InterrogationSession(slug="idea", idea="Idea")
    session.answers = {
        "success_criteria": "successful registration",
        "failure_case": "invalid email rejected",
        "constraints": "password length minimum",
    }

    content = render_draft_gwt(session)
    assert "successful registration" in content
    assert "invalid email rejected" in content
    assert "password length minimum" in content


def test_render_draft_gwt_updates_answer_driven_lines_deterministically() -> None:
    session = InterrogationSession(slug="idea", idea="Idea")
    baseline = render_draft_gwt(session)
    assert "scenario describing" not in baseline

    session.answers["success_criteria"] = "explicit success behavior"
    updated = render_draft_gwt(session)
    assert "explicit success behavior" in updated
    assert updated.count("explicit success behavior") == 1


def _setup_project_with_vocab(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir()
    src_vocab = Path(__file__).resolve().parents[2] / "specs" / "vocab.yaml"
    (tmp_path / "specs" / "vocab.yaml").write_text(src_vocab.read_text())


def test_approval_blocked_until_questions_resolved_and_ir_stable(tmp_path: Path) -> None:
    _setup_project_with_vocab(tmp_path)
    idea = "User registration"

    # Iteration 1: no answers, should not be stable and not approvable.
    session, questions = interrogate_iteration(tmp_path, idea=idea, slug=None, answers={}, approve=False)
    assert questions
    assert not is_ir_stable(session)

    with pytest.raises(InterrogationError, match="unresolved blocking questions"):
        interrogate_iteration(tmp_path, idea=idea, slug=session.slug, answers={}, approve=True)

    # Resolve blocking questions.
    answers = {
        "success_criteria": "user can register with email and password",
        "failure_case": "duplicate email is rejected",
        "constraints": "password must be at least 8 characters",
    }
    session, questions = interrogate_iteration(
        tmp_path, idea=idea, slug=session.slug, answers=answers, approve=False
    )
    # only optional vague-language question may remain
    assert all(not q.blocking for q in questions)

    # Need one more identical compile cycle for stability.
    session, questions = interrogate_iteration(
        tmp_path, idea=idea, slug=session.slug, answers=answers, approve=False
    )
    assert is_ir_stable(session)

    approved, _ = interrogate_iteration(
        tmp_path, idea=idea, slug=session.slug, answers=answers, approve=True
    )
    assert approved.approved
