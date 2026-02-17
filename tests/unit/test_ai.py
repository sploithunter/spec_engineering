"""Unit tests for spec_eng.ai (all Anthropic calls mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from spec_eng.ai import AIError, draft_specs, suggest_gap_fix
from spec_eng.models import Gap, GapType, Severity

pytestmark = pytest.mark.ai


MOCK_DRAFT_RESPONSE = """\
;===============================================================
; User can register with email.
;===============================================================
GIVEN no registered users.

WHEN a user registers with email "bob@example.com".

THEN there is 1 registered user.

;===============================================================
; User can log in after registration.
;===============================================================
GIVEN a registered user.

WHEN the user logs in with correct credentials.

THEN the user is logged in.

;===============================================================
; User can reset password.
;===============================================================
GIVEN a registered user.

WHEN the user requests a password reset.

THEN a password reset link is sent.
"""


def _mock_response(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


class TestDraftSpecs:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("spec_eng.ai.anthropic")
    def test_draft_returns_scenarios(self, mock_anthropic: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(MOCK_DRAFT_RESPONSE)

        scenarios = draft_specs("users can register, log in, and reset passwords")
        assert len(scenarios) == 3

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("spec_eng.ai.anthropic")
    def test_draft_covers_registration(self, mock_anthropic: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(MOCK_DRAFT_RESPONSE)

        scenarios = draft_specs("users can register, log in, and reset passwords")
        titles = [s.title for s in scenarios]
        assert any("register" in t.lower() for t in titles)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("spec_eng.ai.anthropic")
    def test_draft_covers_login(self, mock_anthropic: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(MOCK_DRAFT_RESPONSE)

        scenarios = draft_specs("users can register, log in, and reset passwords")
        titles = [s.title for s in scenarios]
        assert any("log in" in t.lower() for t in titles)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("spec_eng.ai.anthropic")
    def test_draft_covers_password_reset(self, mock_anthropic: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(MOCK_DRAFT_RESPONSE)

        scenarios = draft_specs("users can register, log in, and reset passwords")
        titles = [s.title for s in scenarios]
        assert any("password" in t.lower() for t in titles)

    def test_no_api_key_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            # Remove ANTHROPIC_API_KEY if present
            import os
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with pytest.raises(AIError, match="ANTHROPIC_API_KEY"):
                draft_specs("test")

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("spec_eng.ai.anthropic")
    def test_empty_response_raises(self, mock_anthropic: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        empty_response = MagicMock()
        empty_response.content = []
        mock_client.messages.create.return_value = empty_response

        with pytest.raises(AIError, match="Empty response"):
            draft_specs("test")


class TestSuggestGapFix:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("spec_eng.ai.anthropic")
    def test_suggest_returns_scenarios(self, mock_anthropic: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        suggestion_text = """\
;===============================================================
; User can recover from payment failure.
;===============================================================
GIVEN a payment has failed.

WHEN the user retries the payment.

THEN the payment is processed successfully.
"""
        mock_client.messages.create.return_value = _mock_response(suggestion_text)

        gap = Gap(
            gap_type=GapType.DEAD_END,
            severity=Severity.HIGH,
            description='State "payment failed" has no outbound transitions',
            question="Is this intentional?",
            states=["payment failed"],
        )
        scenarios = suggest_gap_fix(gap)
        assert len(scenarios) >= 1

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("spec_eng.ai.anthropic")
    def test_api_error_raises(self, mock_anthropic: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("Connection failed")

        gap = Gap(
            GapType.DEAD_END, Severity.HIGH, "test", "q?", ["s1"]
        )
        with pytest.raises(AIError, match="API call failed"):
            suggest_gap_fix(gap)
