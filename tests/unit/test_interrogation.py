"""Unit tests for interrogation workflow state and drafting."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_eng.interrogation import (
    InterrogationError,
    InterrogationSession,
    build_questions,
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
