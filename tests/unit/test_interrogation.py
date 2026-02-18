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
