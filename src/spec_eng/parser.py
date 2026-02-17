"""GWT recursive descent parser.

Grammar (informal EBNF):
    file          := scenario* EOF
    scenario      := header clause_block
    header        := HEADER_BAR COMMENT+ HEADER_BAR
    clause_block  := given_section when_section then_section
    given_section := GIVEN_CLAUSE+
    when_section  := WHEN_CLAUSE+
    then_section  := THEN_CLAUSE+
    GIVEN_CLAUSE  := 'GIVEN' text '.'
    WHEN_CLAUSE   := 'WHEN' text '.'
    THEN_CLAUSE   := 'THEN' text '.'
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from spec_eng.models import Clause, ParseError, ParseResult, Scenario


class TokenType(Enum):
    HEADER_BAR = auto()     # ;====...
    COMMENT = auto()        # ; text
    GIVEN = auto()          # GIVEN ... .
    WHEN = auto()           # WHEN ... .
    THEN = auto()           # THEN ... .
    BLANK = auto()          # empty line
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    text: str
    line_number: int


class Lexer:
    """Tokenizes raw GWT text into a token stream."""

    def __init__(self, content: str, source_file: str | None = None) -> None:
        self.lines = content.split("\n")
        self.source_file = source_file

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            stripped = line.strip()
            line_num = i + 1  # 1-indexed

            if not stripped:
                tokens.append(Token(TokenType.BLANK, "", line_num))
                i += 1
                continue

            if stripped.startswith(";") and "===" in stripped:
                tokens.append(Token(TokenType.HEADER_BAR, stripped, line_num))
                i += 1
                continue

            if stripped.startswith(";"):
                # Comment line - extract text after ;
                comment_text = stripped[1:].strip()
                tokens.append(Token(TokenType.COMMENT, comment_text, line_num))
                i += 1
                continue

            # Clause lines: may span multiple lines until terminated by '.'
            clause_type = self._detect_clause_type(stripped)
            if clause_type is not None:
                full_text, end_i = self._read_clause(i)
                tokens.append(Token(clause_type, full_text, line_num))
                i = end_i + 1
                continue

            # Unknown line - skip (will be handled by parser as needed)
            i += 1

        tokens.append(Token(TokenType.EOF, "", len(self.lines) + 1))
        return tokens

    def _detect_clause_type(self, line: str) -> TokenType | None:
        upper = line.upper()
        if upper.startswith("GIVEN "):
            return TokenType.GIVEN
        if upper.startswith("WHEN "):
            return TokenType.WHEN
        if upper.startswith("THEN "):
            return TokenType.THEN
        return None

    def _read_clause(self, start: int) -> tuple[str, int]:
        """Read a clause that may span multiple lines. Returns (text, last_line_index)."""
        parts: list[str] = []
        i = start
        while i < len(self.lines):
            line = self.lines[i].strip()
            if i == start:
                # Remove the keyword prefix
                for prefix in ("GIVEN ", "WHEN ", "THEN "):
                    upper = line.upper()
                    if upper.startswith(prefix):
                        line = line[len(prefix):]
                        break
                    # Handle case-sensitive match
                    if line.startswith(prefix):
                        line = line[len(prefix):]
                        break
            parts.append(line)
            if line.endswith("."):
                break
            i += 1
        text = " ".join(parts)
        # Remove trailing period
        if text.endswith("."):
            text = text[:-1].strip()
        return text, i


class Parser:
    """Recursive descent parser for GWT token streams."""

    def __init__(
        self, tokens: list[Token], source_file: str | None = None
    ) -> None:
        self.tokens = tokens
        self.source_file = source_file
        self.pos = 0
        self.scenarios: list[Scenario] = []
        self.errors: list[ParseError] = []

    def parse(self) -> ParseResult:
        """Parse the token stream into scenarios."""
        self._skip_blanks()

        while not self._at_end():
            if self._peek().type == TokenType.HEADER_BAR:
                self._parse_scenario()
            elif self._peek().type in (TokenType.GIVEN, TokenType.WHEN, TokenType.THEN):
                # Scenario without header
                line = self._peek().line_number
                self._parse_scenario_body(title="Untitled scenario", start_line=line)
            else:
                self._advance()
            self._skip_blanks()

        return ParseResult(scenarios=self.scenarios, errors=self.errors)

    def _parse_scenario(self) -> None:
        """Parse a full scenario (header + clauses)."""
        # Parse header
        title, start_line = self._parse_header()
        if title is None:
            return

        self._skip_blanks()
        self._parse_scenario_body(title=title, start_line=start_line)

    def _parse_header(self) -> tuple[str | None, int]:
        """Parse header bars and comment lines. Returns (title, line_number)."""
        if self._peek().type != TokenType.HEADER_BAR:
            return None, 0

        start_line = self._peek().line_number
        self._advance()  # consume opening bar

        # Collect comment lines for the title
        title_parts: list[str] = []
        while not self._at_end() and self._peek().type == TokenType.COMMENT:
            title_parts.append(self._peek().text)
            self._advance()

        # Consume closing bar if present
        if not self._at_end() and self._peek().type == TokenType.HEADER_BAR:
            self._advance()

        title = " ".join(title_parts).strip()
        return title, start_line

    def _parse_scenario_body(self, title: str, start_line: int) -> None:
        """Parse the clause block of a scenario."""
        self._skip_blanks()

        givens = self._parse_clauses(TokenType.GIVEN, "GIVEN")
        self._skip_blanks()
        whens = self._parse_clauses(TokenType.WHEN, "WHEN")
        self._skip_blanks()
        thens = self._parse_clauses(TokenType.THEN, "THEN")

        scenario = Scenario(
            title=title,
            givens=givens,
            whens=whens,
            thens=thens,
            source_file=self.source_file,
            line_number=start_line,
        )

        validation_errors = scenario.validate()
        if validation_errors:
            for err in validation_errors:
                self.errors.append(ParseError(
                    message=f"{err} (scenario: '{title}')",
                    line_number=start_line,
                    source_file=self.source_file,
                ))
        else:
            self.scenarios.append(scenario)

    def _parse_clauses(self, token_type: TokenType, clause_type: str) -> list[Clause]:
        """Parse one or more consecutive clauses of the given type."""
        clauses: list[Clause] = []
        while not self._at_end() and self._peek().type == token_type:
            token = self._advance()
            clauses.append(Clause(
                clause_type=clause_type,
                text=token.text,
                line_number=token.line_number,
            ))
            self._skip_blanks()
        return clauses

    def _peek(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, "", -1)

    def _advance(self) -> Token:
        token = self._peek()
        self.pos += 1
        return token

    def _at_end(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _skip_blanks(self) -> None:
        while not self._at_end() and self._peek().type == TokenType.BLANK:
            self._advance()


def parse_gwt_string(content: str, source_file: str | None = None) -> ParseResult:
    """Parse a GWT string into a ParseResult."""
    lexer = Lexer(content, source_file)
    tokens = lexer.tokenize()
    parser = Parser(tokens, source_file)
    return parser.parse()


def parse_gwt_file(path: Path) -> ParseResult:
    """Parse a GWT file into a ParseResult."""
    content = path.read_text()
    return parse_gwt_string(content, source_file=str(path))


def parse_markdown_gwt(path: Path) -> ParseResult:
    """Parse GWT scenarios embedded in a Markdown file.

    Looks for lines starting with GIVEN/WHEN/THEN preceded by ;=== headers.
    Also handles indented GWT blocks (e.g., inside SPEC.md scenario descriptions).
    """
    content = path.read_text()
    lines = content.split("\n")

    # Extract GWT blocks: find sections delimited by ;=== headers
    gwt_blocks: list[str] = []
    current_block: list[str] = []
    in_block = False

    for line in lines:
        stripped = line.strip()

        # Start of a GWT scenario header
        if stripped.startswith(";") and "===" in stripped:
            if not in_block:
                in_block = True
                current_block = [stripped]
            else:
                current_block.append(stripped)
            continue

        if in_block:
            if stripped.startswith(";"):
                current_block.append(stripped)
                continue

            # GWT clause lines (possibly indented in markdown)
            upper = stripped.upper()
            if (
                upper.startswith("GIVEN ")
                or upper.startswith("WHEN ")
                or upper.startswith("THEN ")
            ):
                current_block.append(stripped)
                continue

            if stripped == "":
                current_block.append("")
                continue

            # Non-GWT content: check if we had actual clauses
            if any(
                ln.strip().upper().startswith(("GIVEN ", "WHEN ", "THEN "))
                for ln in current_block
            ):
                gwt_blocks.append("\n".join(current_block))
            current_block = []
            in_block = False

    # Handle last block
    if in_block and any(
        ln.strip().upper().startswith(("GIVEN ", "WHEN ", "THEN "))
        for ln in current_block
    ):
        gwt_blocks.append("\n".join(current_block))

    # Parse each block
    all_scenarios: list[Scenario] = []
    all_errors: list[ParseError] = []

    for block in gwt_blocks:
        result = parse_gwt_string(block, source_file=str(path))
        for s in result.scenarios:
            all_scenarios.append(s)
        for e in result.errors:
            all_errors.append(e)

    return ParseResult(scenarios=all_scenarios, errors=all_errors)
