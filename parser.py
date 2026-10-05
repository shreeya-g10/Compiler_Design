# parser.py
# SYNTAX ANALYSIS: checks that the tokens from the lexer follow the grammar
# and builds a list of Relationship objects (our intermediate representation).
#
# Grammar ({ } = repeat zero or more times, [ ] = optional):
#
#     program      → { line } EOF
#     line         → NEWLINE
#                  | relationship NEWLINE
#     relationship → IDENTIFIER ARROW [ SPEED ] [ EVIDENCE ] IDENTIFIER
#
# In words: a line is either empty or one relationship. A relationship is a
# source factor, an arrow, an optional speed, an optional evidence tag, then a
# destination factor. (The very last line may end with EOF instead of NEWLINE.)
#
# This is a RECURSIVE DESCENT parser: there is one method for each grammar rule,
# and each method calls the methods for the rules inside it.
#
# The parser does NOT check whether factors exist in factors.json.
# That is the validator's job.

import sys
from dataclasses import dataclass

from lexer import tokenize


# ---------------------------------------------------------------------------
# 1. The output of the parser: one Relationship per valid line
# ---------------------------------------------------------------------------
@dataclass
class Relationship:
    source: str        # e.g. "CLIMATE"
    destination: str   # e.g. "FOOD"
    speed: str         # "fast", "slow", or None if not written
    evidence: str      # "F", "E", "M", or None if not written
    line: int          # line number in the input file


class ParseError(Exception):
    """Raised when the tokens do not match the grammar."""
    pass


def describe(token):
    """Turn a token into readable text for error messages."""
    if token.type == "NEWLINE":
        return "end of line"
    if token.type == "EOF":
        return "end of file"
    if token.type == "ARROW":
        return "'->'"
    return f"{token.type} '{token.value}'"


# ---------------------------------------------------------------------------
# 2. The recursive descent parser
# ---------------------------------------------------------------------------
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0              # index of the current token
        self.relationships = []   # successfully parsed relationships
        self.errors = []          # syntax error messages

    # ----- helper methods -----

    def current(self):
        """Return the token we are looking at (without consuming it)."""
        return self.tokens[self.pos]

    def advance(self):
        """Consume the current token and return it."""
        token = self.tokens[self.pos]
        if token.type != "EOF":   # never move past EOF
            self.pos += 1
        return token

    def expect(self, token_type, what):
        """The current token MUST be of 'token_type'.
        If it is, consume and return it. If not, raise a ParseError.
        'what' describes what we wanted, used in the error message."""
        token = self.current()
        if token.type == token_type:
            return self.advance()
        raise ParseError(f"Syntax error at line {token.line}, col {token.column}: "
                         f"expected {what} but found {describe(token)}")

    def synchronize(self):
        """PANIC-MODE RECOVERY: skip tokens until the end of the line,
        so we can continue parsing from the next line."""
        while self.current().type not in ("NEWLINE", "EOF"):
            self.advance()
        if self.current().type == "NEWLINE":
            self.advance()

    # ----- one method per grammar rule -----

    def parse_program(self):
        """program → { line } EOF"""
        while self.current().type != "EOF":
            self.parse_line()
        return self.relationships, self.errors

    def parse_line(self):
        """line → NEWLINE | relationship NEWLINE"""
        # Empty line (blank or comment-only): just consume the NEWLINE
        if self.current().type == "NEWLINE":
            self.advance()
            return

        try:
            relationship = self.parse_relationship()
            # After a relationship the line must end (or the file must end)
            if self.current().type != "EOF":
                self.expect("NEWLINE", "end of line after relationship")
            self.relationships.append(relationship)
        except ParseError as error:
            self.errors.append(str(error))
            self.synchronize()

    def parse_relationship(self):
        """relationship → IDENTIFIER ARROW [ SPEED ] [ EVIDENCE ] IDENTIFIER"""
        source = self.expect("IDENTIFIER", "source factor")
        arrow = self.expect("ARROW", f"'->' after '{source.value}'")

        # Optional speed, e.g. (fast)
        speed = None
        last = arrow                          # last token read, for error messages
        if self.current().type == "SPEED":
            last = self.advance()
            speed = last.value.strip("()")    # "(fast)" -> "fast"

        # Optional evidence, e.g. [F]
        evidence = None
        if self.current().type == "EVIDENCE":
            last = self.advance()
            evidence = last.value.strip("[]")  # "[F]" -> "F"

        destination = self.expect("IDENTIFIER", f"destination factor after '{last.value}'")

        return Relationship(source.value, destination.value, speed, evidence, source.line)


def parse(tokens):
    """Parse a list of tokens. Returns (relationships, errors)."""
    return Parser(tokens).parse_program()


# ---------------------------------------------------------------------------
# 3. Demo: venv/bin/python parser.py examples/climate.txt
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parser.py <input_file>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        source_text = f.read()

    # Phase 1: lexical analysis
    tokens, lex_errors = tokenize(source_text)
    for err in lex_errors:
        print(err)
    if lex_errors:
        print()

    # Phase 2: syntax analysis
    relationships, syntax_errors = parse(tokens)

    print(f"{'LINE':<6}{'SOURCE':<17}{'->':<4}{'DESTINATION':<17}{'SPEED':<7}EVIDENCE")
    for r in relationships:
        print(f"{r.line:<6}{r.source:<17}{'->':<4}{r.destination:<17}"
              f"{r.speed or '-':<7}{r.evidence or '-'}")

    print()
    if syntax_errors:
        for err in syntax_errors:
            print(err)
    else:
        print("No syntax errors")
