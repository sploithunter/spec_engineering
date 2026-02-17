"""Shared test fixtures for spec-eng."""

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary empty project directory."""
    return tmp_path


@pytest.fixture
def initialized_project(tmp_path: Path) -> Path:
    """Create a temporary project with spec-eng initialized."""
    spec_eng_dir = tmp_path / ".spec-eng"
    spec_eng_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    config = {
        "version": "0.1.0",
        "language": "python",
        "framework": "pytest",
        "guardian": {
            "enabled": True,
            "sensitivity": "medium",
            "allowlist": [],
        },
        "vocabulary": [],
        "auto_analysis": False,
    }
    (spec_eng_dir / "config.json").write_text(json.dumps(config, indent=2))
    return tmp_path


@pytest.fixture
def sample_gwt_content() -> str:
    """Return a sample GWT spec string."""
    return """\
;===============================================================
; User can register with email and password.
;===============================================================
GIVEN no registered users.

WHEN a user registers with email "bob@example.com" and password "secret123".

THEN there is 1 registered user.
THEN the user "bob@example.com" can log in.
"""


@pytest.fixture
def multi_scenario_gwt() -> str:
    """Return a GWT spec with multiple scenarios."""
    return """\
;===============================================================
; User can register.
;===============================================================
GIVEN no registered users.

WHEN a user registers.

THEN there is 1 registered user.

;===============================================================
; User can log in after registration.
;===============================================================
GIVEN there is 1 registered user.

WHEN the user logs in.

THEN the user is logged in.

;===============================================================
; User can log out.
;===============================================================
GIVEN the user is logged in.

WHEN the user logs out.

THEN the user is logged out.
"""


@pytest.fixture
def sample_gwt_file(tmp_path: Path, sample_gwt_content: str) -> Path:
    """Write sample GWT content to a file and return the path."""
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(exist_ok=True)
    gwt_file = specs_dir / "registration.gwt"
    gwt_file.write_text(sample_gwt_content)
    return gwt_file
