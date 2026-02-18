"""Unit tests for semantic approach evaluator helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_eval_module():
    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    script = root / "scripts" / "eval_semantic_approaches.py"
    spec = importlib.util.spec_from_file_location("eval_semantic_approaches", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_flatten_ir_steps_extracts_kind_symbol_and_arg_keys() -> None:
    mod = _load_eval_module()
    payload = {
        "scenarios": [
            {
                "givens": [{"kind": "fact", "symbol": "a", "args": {"x": "1", "y": "2"}}],
                "whens": [{"kind": "action", "symbol": "b", "args": {"z": "3"}}],
                "thens": [{"kind": "expectation", "symbol": "c", "args": {}}],
            }
        ]
    }

    out = mod._flatten_ir_steps(payload)
    assert ("fact", "a", ("x", "y")) in out
    assert ("action", "b", ("z",)) in out
    assert ("expectation", "c", ()) in out


def test_precision_recall_f1_for_empty_sets() -> None:
    mod = _load_eval_module()
    p, r, f1 = mod._precision_recall_f1(set(), set())
    assert p == 1.0
    assert r == 1.0
    assert f1 == 1.0


def test_flatten_ir_value_terms_extracts_keyed_tokens() -> None:
    mod = _load_eval_module()
    payload = {
        "scenarios": [
            {
                "givens": [{"args": {"concept": "Parse API contract", "count": 1}}],
                "whens": [],
                "thens": [{"args": {"path": "specs/sample.txt"}}],
            }
        ]
    }
    out = mod._flatten_ir_value_terms(payload)
    assert "concept:parse" in out
    assert "concept:contract" in out
    assert "path:specs" in out


def test_coding_ir_first_generates_required_answer_fields() -> None:
    mod = _load_eval_module()
    approach = mod.CodingIRFirst()
    idea, answers = approach.generate(
        owner="octocat",
        repo="sample-repo",
        description="A parser and compiler for specs",
        readme="`parse_spec` and `render_ir` tools for a SpecCompiler service.",
    )

    assert "sample-repo behavior where prototype contracts align around" in idea
    assert set(answers.keys()) == {"success_criteria", "failure_case", "constraints"}
    assert "deterministic and traceable" in answers["constraints"]


def test_summarize_includes_ir_metrics() -> None:
    mod = _load_eval_module()
    row = mod.EvalRow(
        split="eval",
        owner="o",
        repo="r",
        approach="coding-ir-first",
        status="ok",
        approved=True,
        iterations=4,
        alignment_recall=0.2,
        token_overlap=10,
        readme_tokens=50,
        ir_step_precision=0.8,
        ir_step_recall=0.6,
        ir_step_f1=0.686,
        ir_value_precision=0.7,
        ir_value_recall=0.5,
        ir_value_f1=0.583,
    )

    summary = mod.summarize([row])
    key = "coding-ir-first:eval"
    assert key in summary
    assert summary[key]["avg_ir_step_precision_ok"] == 0.8
    assert summary[key]["avg_ir_step_recall_ok"] == 0.6
    assert summary[key]["avg_ir_value_f1_ok"] == 0.583
