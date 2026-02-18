"""Acceptance tests for interrogation-layer dual-spec loop stability."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from spec_eng.dual_spec import check_specs, compile_spec, load_vocab

pytestmark = pytest.mark.acceptance


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_interrogation_layer_roundtrip_stabilizes() -> None:
    root = Path(__file__).resolve().parents[2]
    vocab = load_vocab(root / "specs" / "vocab.yaml")
    source = root / "specs" / "atdd-interrogation-layer.txt"

    compile_spec(source, vocab, project_root=root)
    tracked = [
        root / "specs" / "atdd-interrogation-layer.dal",
        root / "specs" / "atdd-interrogation-layer.txt.canonical",
        root / "acceptance-pipeline" / "ir" / "atdd-interrogation-layer.json",
        root / "acceptance-pipeline" / "roundtrip" / "atdd-interrogation-layer.diff.txt",
    ]
    h1 = {str(p): _digest(p) for p in tracked}

    compile_spec(source, vocab, project_root=root)
    h2 = {str(p): _digest(p) for p in tracked}

    assert h1 == h2


def test_interrogation_layer_has_no_spec_check_violations() -> None:
    root = Path(__file__).resolve().parents[2]
    vocab = load_vocab(root / "specs" / "vocab.yaml")
    violations = check_specs(root / "specs" / "atdd-interrogation-layer.txt", vocab)
    assert violations == []
