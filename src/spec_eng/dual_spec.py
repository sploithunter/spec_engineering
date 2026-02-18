"""Dual-spec compiler for vocab-driven GWT <-> DAL parsing and rendering."""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class DualSpecError(Exception):
    """Raised when vocab/spec compilation fails."""


@dataclass(frozen=True)
class ArgSpec:
    name: str
    type_name: str


@dataclass
class VocabEntry:
    category: str
    symbol: str
    args: list[ArgSpec]
    gwt_patterns: list[re.Pattern[str]]
    gwt_pattern_texts: list[str]
    gwt_render: str
    dal_render: str
    default_args: dict[str, Any] = field(default_factory=dict)
    derive_rules: list[dict[str, Any]] = field(default_factory=list)
    reason_by_match: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Vocab:
    path: Path
    raw: dict[str, Any]
    types: dict[str, dict[str, Any]]
    derivations: dict[str, dict[str, Any]]
    lints: dict[str, Any]
    entries_by_symbol_kind: dict[tuple[str, str], VocabEntry]
    entries_by_kind: dict[str, list[VocabEntry]]


@dataclass(frozen=True)
class StepIR:
    kind: str  # fact | action | expectation
    symbol: str
    args: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "symbol": self.symbol,
            "args": dict(sorted(self.args.items())),
        }


@dataclass(frozen=True)
class ScenarioIR:
    name: str
    imports: list[str]
    givens: list[StepIR]
    whens: list[StepIR]
    thens: list[StepIR]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "imports": list(self.imports),
            "givens": [s.to_dict() for s in self.givens],
            "whens": [s.to_dict() for s in self.whens],
            "thens": [s.to_dict() for s in self.thens],
        }


@dataclass(frozen=True)
class FeatureIR:
    feature_id: str
    scenarios: list[ScenarioIR]

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "scenarios": [s.to_dict() for s in self.scenarios],
        }


@dataclass(frozen=True)
class SpecViolation:
    file: str
    line: int
    column: int
    kind: str
    matched: str
    message: str
    suggestion: str


def load_vocab(vocab_path: Path) -> Vocab:
    """Load and validate vocab.yaml and pre-compile regex matchers."""
    try:
        raw = yaml.safe_load(vocab_path.read_text())
    except yaml.YAMLError as exc:
        raise DualSpecError(f"Invalid YAML in {vocab_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise DualSpecError(f"Invalid vocabulary format in {vocab_path}: expected mapping")

    _require_keys(raw, ["types", "vocabulary", "lints", "gwt", "dal"], "root")
    _require_keys(raw["vocabulary"], ["facts", "actions", "expectations"], "vocabulary")
    _require_keys(raw["lints"], ["implementation_leakage"], "lints")
    _require_keys(raw["gwt"], ["keywords"], "gwt")
    _require_keys(raw["dal"], ["keywords"], "dal")

    entries_by_symbol_kind: dict[tuple[str, str], VocabEntry] = {}
    entries_by_kind: dict[str, list[VocabEntry]] = {"fact": [], "action": [], "expectation": []}

    mappings = [
        ("facts", "fact"),
        ("actions", "action"),
        ("expectations", "expectation"),
    ]
    for vocab_key, kind in mappings:
        entries = raw["vocabulary"][vocab_key]
        if not isinstance(entries, dict):
            raise DualSpecError(f"vocabulary.{vocab_key} must be a mapping")
        for symbol, spec in entries.items():
            entry = _build_vocab_entry(kind, symbol, spec)
            key = (kind, symbol)
            if key in entries_by_symbol_kind:
                raise DualSpecError(f"Duplicate vocabulary symbol '{symbol}' in {kind}")
            entries_by_symbol_kind[key] = entry
            entries_by_kind[kind].append(entry)

    return Vocab(
        path=vocab_path,
        raw=raw,
        types=raw["types"],
        derivations=raw.get("derivations", {}),
        lints=raw["lints"],
        entries_by_symbol_kind=entries_by_symbol_kind,
        entries_by_kind=entries_by_kind,
    )


def _build_vocab_entry(kind: str, symbol: str, spec: dict[str, Any]) -> VocabEntry:
    if not isinstance(spec, dict):
        raise DualSpecError(f"vocabulary entry '{symbol}' must be a mapping")
    _require_keys(spec, ["args", "gwt", "dal"], f"vocabulary entry '{symbol}'")
    _require_keys(spec["gwt"], ["match", "render"], f"vocabulary.{symbol}.gwt")
    _require_keys(spec["dal"], ["render"], f"vocabulary.{symbol}.dal")

    args = []
    for arg in spec["args"]:
        if not isinstance(arg, dict) or "name" not in arg or "type" not in arg:
            raise DualSpecError(f"Invalid arg spec in vocabulary entry '{symbol}'")
        args.append(ArgSpec(name=arg["name"], type_name=arg["type"]))

    gwt_patterns: list[re.Pattern[str]] = []
    gwt_pattern_texts: list[str] = []
    for pattern_text in spec["gwt"]["match"]:
        try:
            gwt_patterns.append(re.compile(pattern_text))
        except re.error as exc:
            raise DualSpecError(f"Invalid regex for '{symbol}': {pattern_text} ({exc})") from exc
        gwt_pattern_texts.append(pattern_text)
    render_pattern = _build_regex_from_render(spec["gwt"]["render"], args)
    if render_pattern is not None:
        gwt_patterns.append(render_pattern)
        gwt_pattern_texts.append(render_pattern.pattern)

    return VocabEntry(
        category=kind,
        symbol=symbol,
        args=args,
        gwt_patterns=gwt_patterns,
        gwt_pattern_texts=gwt_pattern_texts,
        gwt_render=spec["gwt"]["render"],
        dal_render=spec["dal"]["render"],
        default_args=spec.get("default_args", {}),
        derive_rules=spec.get("derive_args_from_context", []),
        reason_by_match=spec.get("reason_by_match", []),
    )


def _build_regex_from_render(template: str, args: list[ArgSpec]) -> re.Pattern[str] | None:
    pattern = re.escape(template)
    for arg in args:
        token = re.escape("{" + arg.name + "}")
        pattern = pattern.replace(token, rf"(?P<{arg.name}>.+?)")
    return re.compile(rf"^{pattern}$")


def _require_keys(data: dict[str, Any], keys: list[str], context: str) -> None:
    for key in keys:
        if key not in data:
            raise DualSpecError(f"Missing required key '{key}' in {context}")


def parse_dal(path: Path, vocab: Vocab) -> FeatureIR:
    """Parse strict DAL into canonical IR."""
    lines = path.read_text().splitlines()
    statements: list[tuple[int, str]] = []
    buffer: list[str] = []
    start_line = 0

    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if not buffer:
            start_line = idx
        buffer.append(stripped)
        if stripped.endswith("."):
            statements.append((start_line, " ".join(buffer)))
            buffer = []

    if buffer:
        raise DualSpecError(f"{path}:{start_line}: DAL statement must end with '.'")

    feature_id = "feature"
    scenarios: list[ScenarioIR] = []
    current: ScenarioIR | None = None

    for line_no, stmt in statements:
        if m := re.fullmatch(r"FEATURE\s+([A-Za-z_][A-Za-z0-9_]*)\.", stmt):
            feature_id = m.group(1)
            continue

        if m := re.fullmatch(r"SCENARIO\s+([a-z][a-z0-9_]*)\.", stmt):
            if current is not None:
                scenarios.append(current)
            name = m.group(1)
            _validate_type(vocab, "scenario_name", name, path, line_no)
            current = ScenarioIR(name=name, imports=[], givens=[], whens=[], thens=[])
            continue

        if m := re.fullmatch(r"IMPORT\s+([a-z][a-z0-9_]*)\.", stmt):
            if current is None:
                raise DualSpecError(f"{path}:{line_no}: IMPORT must appear after SCENARIO")
            current.imports.append(m.group(1))
            continue

        if m := re.fullmatch(r"(FACT|DO|EXPECT)\s+([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)\.", stmt):
            if current is None:
                raise DualSpecError(f"{path}:{line_no}: Step must appear after SCENARIO")
            op, symbol, arg_blob = m.groups()
            step_kind = {"FACT": "fact", "DO": "action", "EXPECT": "expectation"}[op]
            entry = vocab.entries_by_symbol_kind.get((step_kind, symbol))
            if entry is None or entry.category != step_kind:
                raise DualSpecError(f"{path}:{line_no}: Unknown {op} symbol '{symbol}'")
            args = _parse_kwargs(arg_blob, path, line_no)
            _validate_step_args(vocab, entry, args, path, line_no)
            step = StepIR(kind=step_kind, symbol=symbol, args=args)
            if step_kind == "fact":
                current.givens.append(step)
            elif step_kind == "action":
                current.whens.append(step)
            else:
                current.thens.append(step)
            continue

        raise DualSpecError(f"{path}:{line_no}: Invalid DAL statement: {stmt}")

    if current is not None:
        scenarios.append(current)

    return FeatureIR(feature_id=feature_id, scenarios=scenarios)


def _parse_kwargs(text: str, path: Path, line_no: int) -> dict[str, Any]:
    blob = text.strip()
    if not blob:
        return {}

    parts: list[str] = []
    current: list[str] = []
    in_string = False
    escaped = False
    for ch in blob:
        if in_string:
            current.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            current.append(ch)
            continue
        if ch == ",":
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        parts.append("".join(current).strip())

    parsed: dict[str, Any] = {}
    for part in parts:
        if "=" not in part:
            raise DualSpecError(f"{path}:{line_no}: Invalid arg '{part}', expected key=value")
        key, raw_value = part.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        parsed[key] = _parse_value(raw_value, path, line_no)
    return parsed


def _parse_value(raw_value: str, path: Path, line_no: int) -> Any:
    if raw_value.lower() == "true":
        return True
    if raw_value.lower() == "false":
        return False
    if re.fullmatch(r"-?[0-9]+", raw_value):
        return int(raw_value)
    if raw_value.startswith('"') and raw_value.endswith('"'):
        inner = raw_value[1:-1]
        return inner.replace(r'\"', '"').replace(r"\\", "\\")
    raise DualSpecError(f"{path}:{line_no}: Unsupported value '{raw_value}'")


def _validate_step_args(vocab: Vocab, entry: VocabEntry, args: dict[str, Any], path: Path, line_no: int) -> None:
    required = [a.name for a in entry.args]
    for name in required:
        if name not in args:
            raise DualSpecError(f"{path}:{line_no}: Missing arg '{name}' for {entry.symbol}")
    for name in args:
        if name not in required:
            raise DualSpecError(f"{path}:{line_no}: Unexpected arg '{name}' for {entry.symbol}")

    for spec in entry.args:
        _validate_type(vocab, spec.type_name, args[spec.name], path, line_no)


def _validate_type(vocab: Vocab, type_name: str, value: Any, path: Path, line_no: int) -> None:
    type_spec = vocab.types.get(type_name)
    if not type_spec:
        raise DualSpecError(f"{path}:{line_no}: Unknown type '{type_name}'")

    kind = type_spec.get("kind")
    if kind == "string":
        if not isinstance(value, str):
            raise DualSpecError(f"{path}:{line_no}: Expected string for type '{type_name}'")
        pattern = type_spec.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            raise DualSpecError(f"{path}:{line_no}: Value '{value}' does not match type '{type_name}'")
        return

    if kind == "enum":
        if value not in type_spec.get("values", []):
            raise DualSpecError(f"{path}:{line_no}: Value '{value}' not allowed for type '{type_name}'")
        return

    raise DualSpecError(f"{path}:{line_no}: Unsupported type kind '{kind}' for '{type_name}'")


def parse_gwt(path: Path, vocab: Vocab) -> FeatureIR:
    """Parse vocab-driven GWT (.txt) into canonical IR."""
    lines = path.read_text().splitlines()
    stem = path.stem
    if stem.endswith(".txt"):
        stem = stem[:-4]
    feature_id = _slug_to_feature_id(stem)

    scenarios: list[ScenarioIR] = []
    current_name = ""
    givens: list[StepIR] = []
    whens: list[StepIR] = []
    thens: list[StepIR] = []
    imports: list[str] = []

    last_kind: str | None = None
    in_header = False
    header_lines: list[str] = []
    scenario_counter = 0
    context: dict[str, Any] = {}

    def flush() -> None:
        nonlocal current_name, givens, whens, thens, imports, context
        if not (givens or whens or thens):
            return
        scenario_name = current_name or f"scenario_{len(scenarios) + 1}"
        scenarios.append(
            ScenarioIR(
                name=_slug_to_scenario_name(scenario_name),
                imports=list(imports),
                givens=list(givens),
                whens=list(whens),
                thens=list(thens),
            )
        )
        current_name = ""
        givens = []
        whens = []
        thens = []
        imports = []
        context = {
            key: value
            for key, value in context.items()
            if key in {"feature", "feature_slug", "dal_spec_path", "gwt_spec_path"}
        }

    for line_no, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue

        if stripped.startswith(";") and "===" in stripped:
            if in_header:
                current_name = " ".join(header_lines).strip() or current_name
                header_lines = []
                in_header = False
            else:
                if givens or whens or thens:
                    flush()
                in_header = True
                header_lines = []
            continue

        if stripped.startswith(";"):
            if in_header:
                header_lines.append(stripped.lstrip(";").strip())
            continue

        keyword, rest = _split_keyword(stripped, vocab)
        if keyword is None:
            raise DualSpecError(_unknown_gwt_line_error(path, line_no, stripped, vocab))

        if keyword == "AND":
            if last_kind is None:
                raise DualSpecError(f"{path}:{line_no}: AND used before GIVEN/WHEN/THEN")
            kind = last_kind
            canonical_keyword = {"fact": "GIVEN", "action": "WHEN", "expectation": "THEN"}[kind]
            line_for_match = f"{canonical_keyword} {rest}"
        else:
            kind = {"GIVEN": "fact", "WHEN": "action", "THEN": "expectation"}[keyword]
            line_for_match = stripped

        entry, args = _match_gwt_line(line_for_match, kind, vocab)
        if entry is None:
            raise DualSpecError(_unknown_gwt_line_error(path, line_no, stripped, vocab))

        args = _apply_enrichment(entry, args, vocab, context, line_for_match)
        _validate_step_args(vocab, entry, args, path, line_no)
        _update_context(context, args)

        step = StepIR(kind=kind, symbol=entry.symbol, args=args)
        if kind == "fact":
            if whens or thens:
                flush()
            givens.append(step)
        elif kind == "action":
            whens.append(step)
        else:
            thens.append(step)

        if not current_name:
            scenario_counter += 1
            current_name = f"scenario_{scenario_counter}"
        last_kind = kind

    if in_header:
        current_name = " ".join(header_lines).strip() or current_name
    flush()

    return FeatureIR(feature_id=feature_id, scenarios=scenarios)


def _split_keyword(line: str, vocab: Vocab) -> tuple[str | None, str]:
    keywords = vocab.raw["gwt"]["keywords"]
    for key in ("GIVEN", "WHEN", "THEN", "AND"):
        token = keywords.get(key, key)
        prefix = f"{token} "
        if line.startswith(prefix):
            return key, line[len(prefix):]
    return None, ""


def _match_gwt_line(line: str, kind: str, vocab: Vocab) -> tuple[VocabEntry | None, dict[str, Any]]:
    for entry in vocab.entries_by_kind[kind]:
        for idx, pattern in enumerate(entry.gwt_patterns):
            m = pattern.fullmatch(line)
            if not m:
                continue
            args = {k: v for k, v in m.groupdict().items() if v is not None}
            args["_match_index"] = idx
            return entry, args
    return None, {}


def _apply_enrichment(
    entry: VocabEntry,
    args_with_meta: dict[str, Any],
    vocab: Vocab,
    context: dict[str, Any],
    line: str,
) -> dict[str, Any]:
    args = {k: v for k, v in args_with_meta.items() if k != "_match_index"}
    required_arg_names = {spec.name for spec in entry.args}

    for key, value in entry.default_args.items():
        args.setdefault(key, value)

    match_idx = int(args_with_meta.get("_match_index", -1))
    for mapping in entry.reason_by_match:
        if mapping.get("match_index") == match_idx and "reason" in mapping:
            args.setdefault("reason", mapping["reason"])

    # Handle vocab aliases where capture group names differ from typed arg names.
    if "suggestion" in args and "suggestion_contains" in required_arg_names:
        args.setdefault("suggestion_contains", args["suggestion"])
    if "line" in args and "line_contains" in required_arg_names:
        args.setdefault("line_contains", args["line"])
    for alias in ("suggestion", "line"):
        if alias in args and alias not in required_arg_names:
            del args[alias]

    for rule in entry.derive_rules:
        required_group = rule.get("when_match_group_present")
        if required_group and required_group not in args:
            continue
        for target, source in rule.get("derive", {}).items():
            if target in args:
                continue
            if target in context and source == target:
                if target in required_arg_names:
                    args[target] = context[target]
                continue
            value = _resolve_derived_value(target, source, vocab, context, args)
            context[target] = value
            if target in required_arg_names:
                args[target] = value

    for name in required_arg_names:
        if name not in args and name in context:
            args[name] = context[name]
    if (
        "target" in required_arg_names
        and "file" in context
        and args.get("target") == entry.default_args.get("target")
    ):
        args["target"] = context["file"]
    if (
        "file" in required_arg_names
        and "file" in context
        and args.get("file") == entry.default_args.get("file")
    ):
        args["file"] = context["file"]
    if (
        "line_contains" in required_arg_names
        and "line_contains" in args
        and args["line_contains"] == entry.default_args.get("line_contains")
        and "line" in context
    ):
        args["line_contains"] = _line_hint(str(context["line"]))
    if (
        "bad_line_contains" in required_arg_names
        and "bad_line_contains" in args
        and args["bad_line_contains"] == entry.default_args.get("bad_line_contains")
        and "line" in context
    ):
        args["bad_line_contains"] = _bad_line_hint(str(context["line"]))

    if "feature" in args and "feature_slug" not in context:
        context["feature_slug"] = _slugify_kebab(str(args["feature"]))

    if "feature" in args:
        context["feature"] = args["feature"]

    # Allow inline text capture that lacks terminal period in source patterns.
    if "suggestion" in args and isinstance(args["suggestion"], str):
        args["suggestion"] = args["suggestion"].rstrip()

    return {k: v for k, v in args.items() if k in required_arg_names}


def _resolve_derived_value(
    target: str,
    source: Any,
    vocab: Vocab,
    context: dict[str, Any],
    args: dict[str, Any],
) -> Any:
    if isinstance(source, str):
        if source in args:
            return args[source]
        if source in context:
            return context[source]
        if source in vocab.derivations:
            derivation = vocab.derivations[source]
            if derivation.get("transform") == "slugify_kebab":
                feature = str(args.get("feature") or context.get("feature") or "feature")
                value = _slugify_kebab(feature)
                context[source] = value
                return value
            if "format" in derivation:
                fmt = derivation["format"]
                format_ctx = {**context, **args}
                if "feature_slug" not in format_ctx:
                    feature = str(format_ctx.get("feature") or context.get("feature") or "feature")
                    format_ctx["feature_slug"] = _slugify_kebab(feature)
                value = fmt.format(**format_ctx)
                context[source] = value
                return value
        return source

    return source


def _update_context(context: dict[str, Any], args: dict[str, Any]) -> None:
    for key, value in args.items():
        if key in {"feature", "feature_slug", "file", "gwt", "dal", "source", "from", "target", "scenario", "line"}:
            context[key] = value
        if key == "file" and isinstance(value, str):
            if value.endswith(".dal"):
                context["dal_spec_path"] = value
            if value.endswith(".txt"):
                context["gwt_spec_path"] = value
        if key in {"path", "gwt", "dal"} and isinstance(value, str):
            if value.endswith(".dal"):
                context["dal_spec_path"] = value
            if value.endswith(".txt"):
                context["gwt_spec_path"] = value


def _line_hint(line: str) -> str:
    api_match = re.search(r"/api/[A-Za-z0-9_/-]+", line)
    if api_match:
        return api_match.group(0)
    camel_match = re.search(r"[A-Z][A-Za-z0-9]*(Service|Repository|Controller)", line)
    if camel_match:
        return camel_match.group(0)
    snake_match = re.search(r"[a-z]+_[a-z_]*", line)
    if snake_match:
        snake = snake_match.group(0)
        if "_has_" in snake:
            return "_".join(snake.split("_")[:2])
        return snake
    token_match = re.search(r"[A-Za-z0-9_/.-]+", line)
    if token_match:
        return token_match.group(0)
    return line


def _bad_line_hint(line: str) -> str:
    fact_match = re.search(r"FACT\s+([a-z][a-z0-9_]*)", line)
    if fact_match:
        return fact_match.group(1)
    return _line_hint(line)


def _unknown_gwt_line_error(path: Path, line_no: int, line: str, vocab: Vocab) -> str:
    candidates = [
        entry.gwt_render
        for entry in vocab.entries_by_symbol_kind.values()
    ]
    nearby = difflib.get_close_matches(line, candidates, n=3, cutoff=0.25)
    suffix = f" Closest candidates: {', '.join(nearby)}" if nearby else ""
    return f"{path}:{line_no}: Could not match GWT line: {line}.{suffix}"


def render_dal(ir: FeatureIR, vocab: Vocab) -> str:
    """Render canonical DAL from IR."""
    lines = [
        "; GENERATED FILE - DO NOT EDIT",
        "; source of truth is IR and vocab-driven compiler",
        "",
        f"FEATURE {ir.feature_id}.",
        "",
    ]

    for scenario in ir.scenarios:
        lines.append(f"SCENARIO {scenario.name}.")
        lines.append("")

        for imported in scenario.imports:
            lines.append(f"IMPORT {imported}.")
        if scenario.imports:
            lines.append("")

        for step in scenario.givens + scenario.whens + scenario.thens:
            lines.append(_render_dal_step(step, vocab))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_dal_step(step: StepIR, vocab: Vocab) -> str:
    entry = vocab.entries_by_symbol_kind[(step.kind, step.symbol)]
    ordered_args = _ordered_args(entry, step.args)
    arg_text = ", ".join(f"{key}={_render_value(value)}" for key, value in ordered_args)
    prefix = {"fact": "FACT", "action": "DO", "expectation": "EXPECT"}[step.kind]
    return f"{prefix} {step.symbol}({arg_text})."


def render_gwt(ir: FeatureIR, vocab: Vocab) -> str:
    """Render canonical GWT from IR using vocab templates."""
    bar = ";==============================================================="
    lines = [
        "; GENERATED FILE - DO NOT EDIT",
        "; canonicalized from DAL/IR using vocab.yaml",
        "",
    ]

    for scenario in ir.scenarios:
        title = scenario.name.replace("_", " ").strip().capitalize() + "."
        lines.extend([bar, f"; {title}", bar])

        for step in scenario.givens:
            lines.append(_render_gwt_step(step, vocab))
        lines.append("")

        for step in scenario.whens:
            lines.append(_render_gwt_step(step, vocab))
        lines.append("")

        for step in scenario.thens:
            lines.append(_render_gwt_step(step, vocab))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_gwt_step(step: StepIR, vocab: Vocab) -> str:
    entry = vocab.entries_by_symbol_kind[(step.kind, step.symbol)]
    if "reason" in step.args and entry.reason_by_match:
        reason_value = step.args["reason"]
        for mapping in entry.reason_by_match:
            if mapping.get("reason") != reason_value:
                continue
            match_index = mapping.get("match_index")
            if isinstance(match_index, int) and 0 <= match_index < len(entry.gwt_pattern_texts):
                rendered = _regex_literal_to_text(entry.gwt_pattern_texts[match_index])
                if rendered is not None:
                    return rendered
    template = _pick_gwt_template(entry, step.args)
    template_args = dict(step.args)
    for placeholder in re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", template):
        if placeholder in template_args:
            continue
        contains_name = f"{placeholder}_contains"
        if contains_name in template_args:
            template_args[placeholder] = template_args[contains_name]
    try:
        return template.format(**template_args)
    except KeyError:
        # Fallback for templates requiring alternate names that are not arguments.
        return template


def _pick_gwt_template(entry: VocabEntry, args: dict[str, Any]) -> str:
    required_names = [spec.name for spec in entry.args]
    if _template_covers_required(entry.gwt_render, required_names, entry.default_args):
        return entry.gwt_render

    for pattern_text in entry.gwt_pattern_texts:
        template = _pattern_to_template(pattern_text)
        if template and _template_covers_required(template, required_names, entry.default_args):
            return template
    return entry.gwt_render


def _template_covers_required(
    template: str,
    required: list[str],
    defaults: dict[str, Any],
) -> bool:
    placeholders = set(re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", template))
    return all(name in placeholders or name in defaults for name in required)


def _pattern_to_template(pattern: str) -> str | None:
    text = pattern.strip()
    if text.startswith("^"):
        text = text[1:]
    if text.endswith("$"):
        text = text[:-1]
    if "|" in text:
        return None
    text = re.sub(r"\(\?P<([a-zA-Z_][a-zA-Z0-9_]*)>[^)]+\)", r"{\1}", text)
    text = text.replace(r"\.", ".").replace(r"\s+", " ").replace(r"\\", "\\")
    if "(?P<" in text:
        return None
    return text


def _regex_literal_to_text(pattern: str) -> str | None:
    text = pattern.strip()
    if text.startswith("^"):
        text = text[1:]
    if text.endswith("$"):
        text = text[:-1]
    if "(?P<" in text or "|" in text or "+" in text or "*" in text:
        return None
    return text.replace(r"\.", ".").replace(r"\\", "\\")


def _ordered_args(entry: VocabEntry, args: dict[str, Any]) -> list[tuple[str, Any]]:
    ordered: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for spec in entry.args:
        if spec.name in args:
            ordered.append((spec.name, args[spec.name]))
            seen.add(spec.name)
    for key in sorted(args):
        if key not in seen:
            ordered.append((key, args[key]))
    return ordered


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', r'\"')
        return f'"{escaped}"'
    raise DualSpecError(f"Unsupported DAL arg value type: {type(value).__name__}")


def serialize_ir_json(ir: FeatureIR) -> str:
    return json.dumps(ir.to_dict(), indent=2, sort_keys=True) + "\n"


def compile_spec(input_path: Path, vocab: Vocab, project_root: Path | None = None) -> dict[str, Path]:
    """Compile .txt/.dal spec into canonical outputs and IR artifacts."""
    project_root = project_root or Path.cwd()
    specs_dir = project_root / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    ir_dir = project_root / "acceptance-pipeline" / "ir"
    ir_dir.mkdir(parents=True, exist_ok=True)
    roundtrip_dir = project_root / "acceptance-pipeline" / "roundtrip"
    roundtrip_dir.mkdir(parents=True, exist_ok=True)

    slug = input_path.stem
    outputs: dict[str, Path] = {}

    if input_path.suffix == ".txt":
        ir = parse_gwt(input_path, vocab)
        dal_text = render_dal(ir, vocab)
        canonical_gwt = render_gwt(ir, vocab)

        dal_path = specs_dir / f"{slug}.dal"
        canonical_path = specs_dir / f"{slug}.txt.canonical"
        ir_path = ir_dir / f"{slug}.json"
        diff_path = roundtrip_dir / f"{slug}.diff.txt"

        dal_path.write_text(dal_text)
        canonical_path.write_text(canonical_gwt)
        ir_path.write_text(serialize_ir_json(ir))
        diff_path.write_text(_unified_diff(input_path.read_text(), canonical_gwt, str(input_path), str(canonical_path)))

        canonical_ir = parse_gwt(canonical_path, vocab)
        if canonical_ir.to_dict() != ir.to_dict():
            raise DualSpecError(
                f"Roundtrip gate failed: IR mismatch for {input_path} vs {canonical_path}"
            )

        outputs.update({
            "dal": dal_path,
            "canonical_gwt": canonical_path,
            "ir": ir_path,
            "diff": diff_path,
        })
        return outputs

    if input_path.suffix == ".dal":
        ir = parse_dal(input_path, vocab)
        canonical_gwt = render_gwt(ir, vocab)
        canonical_path = specs_dir / f"{slug}.txt.canonical"
        ir_path = ir_dir / f"{slug}.json"

        canonical_path.write_text(canonical_gwt)
        ir_path.write_text(serialize_ir_json(ir))

        outputs.update({"canonical_gwt": canonical_path, "ir": ir_path})
        return outputs

    raise DualSpecError(f"Unsupported input extension for {input_path}; expected .txt or .dal")


def _unified_diff(original: str, canonical: str, from_name: str, to_name: str) -> str:
    diff = difflib.unified_diff(
        original.splitlines(),
        canonical.splitlines(),
        fromfile=from_name,
        tofile=to_name,
        lineterm="",
    )
    content = "\n".join(diff).strip()
    if not content:
        return "No textual differences.\n"
    return content + "\n"


def check_specs(target: Path, vocab: Vocab) -> list[SpecViolation]:
    """Run implementation leakage checks from vocab lints."""
    lint = vocab.lints["implementation_leakage"]
    banned_tokens: list[str] = lint.get("banned_tokens", [])
    banned_regex: list[str] = lint.get("banned_regex", [])
    allowed_contextual: set[str] = set(lint.get("allowed_contextual_tokens", []))

    regexes = [re.compile(p) for p in banned_regex]
    identifier_regex = re.compile(
        r"\b[A-Za-z_]*(service|repository|controller|dao|orm|method|function|class)\b",
        re.IGNORECASE,
    )

    files = _collect_spec_files(target)
    violations: list[SpecViolation] = []

    for file_path in files:
        for line_no, raw in enumerate(file_path.read_text().splitlines(), start=1):
            if not raw.strip() or raw.strip().startswith(";"):
                continue
            line = raw.rstrip("\n")

            for token in banned_tokens:
                if token.lower() in allowed_contextual:
                    continue
                pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
                for match in pattern.finditer(line):
                    violations.append(
                        SpecViolation(
                            file=str(file_path),
                            line=line_no,
                            column=match.start() + 1,
                            kind="token",
                            matched=match.group(0),
                            message=f"Implementation token '{match.group(0)}' is banned",
                            suggestion=_suggest_rewrite(line),
                        )
                    )

            for match in identifier_regex.finditer(line):
                violations.append(
                    SpecViolation(
                        file=str(file_path),
                        line=line_no,
                        column=match.start() + 1,
                        kind="identifier",
                        matched=match.group(0),
                        message=f"Implementation identifier '{match.group(0)}' is banned",
                        suggestion=_suggest_rewrite(line),
                    )
                )

            for pattern in regexes:
                for match in pattern.finditer(line):
                    violations.append(
                        SpecViolation(
                            file=str(file_path),
                            line=line_no,
                            column=match.start() + 1,
                            kind="regex",
                            matched=match.group(0),
                            message=f"Implementation pattern matched: {pattern.pattern}",
                            suggestion=_suggest_rewrite(line),
                        )
                    )

    return _dedupe_violations(violations)


def _collect_spec_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]

    files = []
    for suffix in ("*.txt", "*.dal"):
        files.extend(sorted(target.rglob(suffix)))
    return files


def _suggest_rewrite(line: str) -> str:
    lower = line.lower()
    if "userservice" in lower or "repository" in lower or "user_repository" in lower:
        return "GIVEN no registered users."
    if "/api/" in lower or any(v in line for v in ["GET", "POST", "PUT", "PATCH", "DELETE"]):
        return 'WHEN a user registers with email "bob@example.com" and password "secret123".'
    return "Rewrite this line as behavioral intent without implementation details."


def _dedupe_violations(violations: list[SpecViolation]) -> list[SpecViolation]:
    seen: set[tuple[str, int, int, str, str]] = set()
    deduped: list[SpecViolation] = []
    for violation in violations:
        key = (violation.file, violation.line, violation.column, violation.kind, violation.matched)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(violation)
    return deduped


def load_feature_ir(path: Path) -> FeatureIR:
    """Load feature IR JSON written by compile_spec."""
    data = json.loads(path.read_text())
    scenarios: list[ScenarioIR] = []
    for scenario in data.get("scenarios", []):
        scenarios.append(
            ScenarioIR(
                name=scenario["name"],
                imports=scenario.get("imports", []),
                givens=[_step_from_dict(s) for s in scenario.get("givens", [])],
                whens=[_step_from_dict(s) for s in scenario.get("whens", [])],
                thens=[_step_from_dict(s) for s in scenario.get("thens", [])],
            )
        )
    return FeatureIR(feature_id=data["feature_id"], scenarios=scenarios)


def _step_from_dict(data: dict[str, Any]) -> StepIR:
    return StepIR(kind=data["kind"], symbol=data["symbol"], args=data.get("args", {}))


def _slugify_kebab(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-") or "feature"


def _slug_to_feature_id(slug: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_") or "feature"


def _slug_to_scenario_name(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_") or "scenario"
