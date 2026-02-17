"""Acceptance tests for Section 3: Spec Guardian.

Covers: 3.1 - 3.8.
"""

import json
from pathlib import Path

import pytest

from spec_eng.guardian import analyze_clause, analyze_scenario
from spec_eng.models import Clause, Scenario

pytestmark = pytest.mark.acceptance


class TestScenario3_1:
    """3.1: The guardian detects class/module names in specs."""

    def test_warns_for_userservice(self) -> None:
        clause = Clause("GIVEN", "the UserService has no users", 1)
        warnings = analyze_clause(clause)
        flagged = [t for w in warnings for t in w.flagged_terms]
        assert any("UserService" in t for t in flagged)

    def test_suggests_behavioral_alternative(self) -> None:
        clause = Clause("GIVEN", "the UserService has no users", 1)
        warnings = analyze_clause(clause)
        suggestions = [w.suggested_alternative for w in warnings]
        assert any("user" in s.lower() for s in suggestions)

    def test_does_not_modify_original(self) -> None:
        clause = Clause("GIVEN", "the UserService has no users", 1)
        original = clause.text
        analyze_clause(clause)
        assert clause.text == original


class TestScenario3_2:
    """3.2: The guardian detects database terminology."""

    def test_warns_for_table_and_row(self) -> None:
        clause = Clause("THEN", "the users table contains 1 row", 1)
        warnings = analyze_clause(clause)
        flagged = [t for w in warnings for t in w.flagged_terms]
        assert any("table" in t.lower() for t in flagged)
        assert any("row" in t.lower() for t in flagged)

    def test_suggests_behavioral(self) -> None:
        clause = Clause("THEN", "the users table contains 1 row", 1)
        warnings = analyze_clause(clause)
        suggestions = [w.suggested_alternative for w in warnings]
        assert any("user" in s.lower() or "record" in s.lower() for s in suggestions)


class TestScenario3_3:
    """3.3: The guardian detects API/protocol terminology."""

    def test_warns_for_post_request(self) -> None:
        clause = Clause("WHEN", "a POST request is sent to /api/users", 1)
        warnings = analyze_clause(clause)
        flagged = [t for w in warnings for t in w.flagged_terms]
        assert any("POST" in t for t in flagged) or any("/api/" in t for t in flagged)

    def test_suggests_behavioral(self) -> None:
        clause = Clause("WHEN", "a POST request is sent to /api/users", 1)
        warnings = analyze_clause(clause)
        suggestions = [w.suggested_alternative for w in warnings]
        assert any("register" in s.lower() or "action" in s.lower() for s in suggestions)


class TestScenario3_4:
    """3.4: The guardian detects framework-specific terminology."""

    def test_warns_for_redis_cache(self) -> None:
        clause = Clause("GIVEN", "the Redis cache is empty", 1)
        warnings = analyze_clause(clause)
        flagged = [t for w in warnings for t in w.flagged_terms]
        assert any("Redis" in t for t in flagged)

    def test_suggests_behavioral(self) -> None:
        clause = Clause("GIVEN", "the Redis cache is empty", 1)
        warnings = analyze_clause(clause)
        suggestions = [w.suggested_alternative for w in warnings]
        assert any("cache" in s.lower() or "session" in s.lower() for s in suggestions)


class TestScenario3_5:
    """3.5: The guardian accepts pure behavioral language."""

    def test_no_warnings_for_behavioral(self) -> None:
        scenario = Scenario(
            title="Clean spec",
            givens=[Clause("GIVEN", "no registered users", 1)],
            whens=[
                Clause(
                    "WHEN",
                    'a user registers with email "bob@example.com" and password "secret123"',
                    3,
                )
            ],
            thens=[Clause("THEN", "there is 1 registered user", 5)],
        )
        warnings = analyze_scenario(scenario)
        assert len(warnings) == 0


class TestScenario3_6:
    """3.6: The guardian runs automatically on spec save.

    This tests the analysis function itself; the auto-run-on-save
    behavior is an integration concern tested via CLI in later phases.
    """

    def test_analysis_completes_quickly(self) -> None:
        import time

        clause = Clause("GIVEN", "the UserService has no users", 1)
        start = time.time()
        analyze_clause(clause)
        elapsed = time.time() - start
        assert elapsed < 2.0  # Well within 2 second budget


class TestScenario3_7:
    """3.7: The guardian can be configured with project-specific allowlists."""

    def test_allowlisted_term_not_flagged(self) -> None:
        clause = Clause("GIVEN", "the user has an API key", 1)
        warnings = analyze_clause(clause, allowlist=["API key"])
        # "API" alone might still be caught, but "API key" should be allowed
        flagged = [t for w in warnings for t in w.flagged_terms]
        # No warnings should reference "API" when "API key" is allowlisted
        assert not any("API" in t for t in flagged)


class TestScenario3_8:
    """3.8: Guardian suggestions require human approval.

    The guardian produces warnings but does NOT auto-modify specs.
    This test verifies the structural contract.
    """

    def test_warnings_are_suggestions_not_modifications(self) -> None:
        clause = Clause("GIVEN", "the UserService has no users", 1)
        original = clause.text
        warnings = analyze_clause(clause)
        # Warnings exist
        assert len(warnings) > 0
        # Each has a suggestion
        for w in warnings:
            assert w.suggested_alternative
        # Original is unmodified
        assert clause.text == original

    def test_each_warning_reviewable_individually(self) -> None:
        scenario = Scenario(
            title="Test",
            givens=[Clause("GIVEN", "the UserService is running", 1)],
            whens=[Clause("WHEN", "a POST request is sent to /api/users", 3)],
            thens=[Clause("THEN", "the users table has 1 row", 5)],
        )
        warnings = analyze_scenario(scenario)
        # Should have multiple independent warnings
        assert len(warnings) >= 2
        # Each is a separate warning object with its own fields
        for w in warnings:
            assert w.original_text
            assert w.flagged_terms
            assert w.suggested_alternative
