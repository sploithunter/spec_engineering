"""Unit tests for vocab-driven dual-spec compiler."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from spec_eng.dual_spec import (
    DualSpecError,
    check_specs,
    compile_spec,
    load_vocab,
    parse_dal,
    parse_gwt,
    render_dal,
    render_gwt,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def vocab(repo_root: Path):
    return load_vocab(repo_root / "specs" / "vocab.yaml")


def test_load_vocab_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "vocab.yaml"
    path.write_text("types: [unterminated")

    with pytest.raises(DualSpecError, match="Invalid YAML"):
        load_vocab(path)


def test_load_vocab_missing_required_key(tmp_path: Path) -> None:
    path = tmp_path / "vocab.yaml"
    path.write_text("types: {}\nvocabulary: {}\nlints: {}\n")

    with pytest.raises(DualSpecError, match="Missing required key"):
        load_vocab(path)


def test_load_vocab_invalid_regex(tmp_path: Path) -> None:
    path = tmp_path / "vocab.yaml"
    path.write_text(
        """
version: 0.1
gwt:
  keywords: {GIVEN: GIVEN, WHEN: WHEN, THEN: THEN, AND: AND}
dal:
  keywords: [FEATURE, SCENARIO, FACT, DO, EXPECT, IMPORT]
types:
  text: {kind: string, pattern: '^.*$'}
lints:
  implementation_leakage: {banned_tokens: [], banned_regex: []}
vocabulary:
  facts:
    broken:
      args: []
      gwt:
        match: ['^(invalid(']
        render: 'GIVEN broken.'
      dal:
        render: 'FACT broken().'
  actions: {}
  expectations: {}
"""
    )

    with pytest.raises(DualSpecError, match="Invalid regex"):
        load_vocab(path)


def test_dal_to_ir_to_dal_is_idempotent(repo_root: Path, vocab) -> None:
    dal_path = repo_root / "tests" / "fixtures" / "dual-spec-sample.dal"

    ir = parse_dal(dal_path, vocab)
    canonical_once = render_dal(ir, vocab)

    tmp = repo_root / "specs" / "_tmp_idempotence_test.dal"
    try:
        tmp.write_text(canonical_once)
        ir_again = parse_dal(tmp, vocab)
        canonical_twice = render_dal(ir_again, vocab)
    finally:
        if tmp.exists():
            tmp.unlink()

    assert ir.to_dict() == ir_again.to_dict()
    assert canonical_once == canonical_twice


def test_gwt_ir_equals_dal_ir_for_equivalent_fixtures(repo_root: Path, vocab) -> None:
    gwt_path = repo_root / "tests" / "fixtures" / "dual-spec-sample.txt"
    dal_path = repo_root / "tests" / "fixtures" / "dual-spec-sample.dal"

    gwt_ir = parse_gwt(gwt_path, vocab)
    dal_ir = parse_dal(dal_path, vocab)

    assert gwt_ir.to_dict() == dal_ir.to_dict()


def test_gwt_dal_gwt_roundtrip_is_stable(repo_root: Path, vocab) -> None:
    gwt_path = repo_root / "tests" / "fixtures" / "dual-spec-sample.txt"

    ir = parse_gwt(gwt_path, vocab)
    dal_text = render_dal(ir, vocab)

    tmp_dal = repo_root / "specs" / "_tmp_roundtrip_test.dal"
    try:
        tmp_dal.write_text(dal_text)
        ir_from_dal = parse_dal(tmp_dal, vocab)
        canonical_1 = render_gwt(ir_from_dal, vocab)
        canonical_2 = render_gwt(ir_from_dal, vocab)
    finally:
        if tmp_dal.exists():
            tmp_dal.unlink()

    assert canonical_1 == canonical_2


def test_compile_spec_writes_expected_outputs(tmp_path: Path, repo_root: Path) -> None:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True)
    shutil.copy(repo_root / "specs" / "vocab.yaml", specs_dir / "vocab.yaml")
    shutil.copy(repo_root / "tests" / "fixtures" / "dual-spec-sample.txt", specs_dir / "sample.txt")

    vocab = load_vocab(specs_dir / "vocab.yaml")
    outputs = compile_spec(specs_dir / "sample.txt", vocab, project_root=tmp_path)

    assert outputs["dal"].exists()
    assert outputs["canonical_gwt"].exists()
    assert outputs["ir"].exists()
    assert outputs["diff"].exists()


def test_spec_check_flags_banned_tokens_and_regex(tmp_path: Path, repo_root: Path) -> None:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True)
    shutil.copy(repo_root / "specs" / "vocab.yaml", specs_dir / "vocab.yaml")

    leaky = specs_dir / "leaky.txt"
    leaky.write_text(
        "\n".join(
            [
                "GIVEN the UserService has an empty userRepository.",
                "WHEN a POST request is sent to /api/users with JSON body.",
            ]
        )
        + "\n"
    )

    vocab = load_vocab(specs_dir / "vocab.yaml")
    violations = check_specs(leaky, vocab)

    assert violations
    assert any("UserService" in v.matched for v in violations)
    assert any("POST" in v.matched or "/api/" in v.matched for v in violations)
    assert any(v.suggestion for v in violations)
