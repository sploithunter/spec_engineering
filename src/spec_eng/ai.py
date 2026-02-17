"""Anthropic Claude API integration for spec drafting and gap suggestions."""

from __future__ import annotations

import os

import anthropic

from spec_eng.models import Gap, Scenario
from spec_eng.parser import parse_gwt_string

SYSTEM_PROMPT = """\
You are a behavioral specification expert. You write Given/When/Then (GWT) \
specifications that describe WHAT a system does, never HOW it does it.

Rules:
- Use only behavioral language (no class names, no database terms, no API routes)
- Each scenario must have GIVEN, WHEN, and THEN clauses
- Clauses end with a period
- Scenarios are separated by header comment bars

Format each scenario exactly like this:
;===============================================================
; <Title describing the behavior>.
;===============================================================
GIVEN <precondition>.

WHEN <action or event>.

THEN <expected outcome>.
"""


class AIError(Exception):
    """Raised when AI operations fail."""


def _get_client() -> anthropic.Anthropic:
    """Get an Anthropic client, raising clear errors."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise AIError(
            "No ANTHROPIC_API_KEY environment variable set. "
            "Set it to use AI features, or use spec-eng without AI."
        )

    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        raise AIError(f"Failed to create Anthropic client: {e}")


def draft_specs(description: str) -> list[Scenario]:
    """Use Claude to draft GWT specs from a natural language description.

    Returns a list of parsed Scenario objects.
    """
    client = _get_client()

    prompt = (
        f"Write GWT behavioral specifications for the following:\n\n"
        f"{description}\n\n"
        f"Generate separate scenarios for each distinct behavior. "
        f"Include both happy paths and error cases. "
        f"Use only behavioral language - no implementation details."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise AIError(f"API call failed: {e}")

    # Extract text from response
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    if not text:
        raise AIError("Empty response from Claude")

    # Parse the generated GWT content
    result = parse_gwt_string(text, source_file="<ai-draft>")
    return result.scenarios


def suggest_gap_fix(gap: Gap) -> list[Scenario]:
    """Use Claude to suggest GWT scenarios to fill a gap.

    Returns a list of parsed Scenario objects.
    """
    client = _get_client()

    prompt = (
        f"A gap analysis found the following issue in a behavioral specification:\n\n"
        f"Type: {gap.gap_type.value}\n"
        f"Description: {gap.description}\n"
        f"Question: {gap.question}\n"
        f"Related states: {', '.join(gap.states)}\n\n"
        f"Write GWT scenarios that would address this gap. "
        f"Use only behavioral language."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise AIError(f"API call failed: {e}")

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    if not text:
        raise AIError("Empty response from Claude")

    result = parse_gwt_string(text, source_file="<ai-suggestion>")
    return result.scenarios
