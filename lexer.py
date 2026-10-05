# lexer.py
# LEXICAL ANALYSIS: converts the input text into a list of tokens
# (FACTOR names, arrows "->", speed like (fast)/(slow), evidence like [F]/[E]/[M]).
#
# The lexer only checks that each piece of text is a valid "word" of the language.
# It does NOT check grammar (e.g. a missing arrow) - that is the parser's job.
# It does NOT check meaning (e.g. an unknown factor) - that is the validator's job.

import re
import sys
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 1. The Token class
# ---------------------------------------------------------------------------
@dataclass
class Token:
    type: str     # kind of token, e.g. "IDENTIFIER" or "ARROW"
    value: str    # the actual text, e.g. "CLIMATE" or "->"
    line: int     # line number where the token starts (1-based)
    column: int   # column number where the token starts (1-based)


# ---------------------------------------------------------------------------
# 2. The token table: (TOKEN_TYPE, regex) pairs
#    These are the ONLY real tokens of our language.
# ---------------------------------------------------------------------------
TOKEN_SPEC = [
    # \b at the end makes sure the whole word is uppercase,
    # so "Climate" is NOT split into "C" + "limate".
    ("IDENTIFIER", r"[A-Z][A-Z0-9_]*\b"),
    ("ARROW",      r"->"),
    ("SPEED",      r"\((fast|slow)\)"),
    ("EVIDENCE",   r"\[(F|E|M)\]"),
    ("NEWLINE",    r"\n"),
]

# Extra patterns the lexer needs, but which do NOT become tokens.
# They are tried AFTER the real tokens, so they only match what is left over.
SKIP_AND_ERROR_SPEC = [
    ("SKIP",        r"[ \t\r]+"),                # spaces and tabs -> ignore
    ("COMMENT",     r"#[^\n]*"),                 # from # to end of line -> ignore
    ("BAD_WORD",    r"[A-Za-z_][A-Za-z0-9_]*"),  # e.g. "climate" -> error
    ("BAD_BRACKET", r"\([^()\[\]\s]*\)?|\[[^()\[\]\s]*\]?"),  # e.g. "(medium)", "[X]" -> error
    ("MISMATCH",    r"."),                       # any other single character -> error
]

# Build ONE combined regex like: (?P<IDENTIFIER>...)|(?P<ARROW>...)|...
# Python tries the alternatives in order, left to right.
MASTER_PATTERN = re.compile(
    "|".join(f"(?P<{name}>{regex})" for name, regex in TOKEN_SPEC + SKIP_AND_ERROR_SPEC)
)


# ---------------------------------------------------------------------------
# 3. The tokenize function
# ---------------------------------------------------------------------------
def tokenize(text):
    """Turn input text into a list of tokens.

    Returns (tokens, errors):
      tokens - list of Token objects, always ending with an EOF token
      errors - list of error message strings (empty if everything is fine)
    """
    tokens = []
    errors = []
    line = 1          # current line number
    line_start = 0    # index in 'text' where the current line begins

    # finditer scans the text from start to end, one match at a time
    for match in MASTER_PATTERN.finditer(text):
        kind = match.lastgroup                     # which named pattern matched
        value = match.group()                      # the matched text
        column = match.start() - line_start + 1    # 1-based column

        if kind == "NEWLINE":
            tokens.append(Token(kind, "\\n", line, column))
            line += 1
            line_start = match.end()
        elif kind in ("SKIP", "COMMENT"):
            pass  # ignore whitespace and comments
        elif kind == "BAD_WORD":
            errors.append(f"Lexical error at line {line}, col {column}: "
                          f"unexpected '{value}' (factors must be UPPERCASE)")
        elif kind in ("BAD_BRACKET", "MISMATCH"):
            errors.append(f"Lexical error at line {line}, col {column}: "
                          f"unexpected '{value}'")
        else:
            # A real token: IDENTIFIER, ARROW, SPEED or EVIDENCE
            tokens.append(Token(kind, value, line, column))

    # Mark the end of the input
    tokens.append(Token("EOF", "", line, len(text) - line_start + 1))
    return tokens, errors


# ---------------------------------------------------------------------------
# 4. Demo: python lexer.py examples/climate.txt
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python lexer.py <input_file>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        source = f.read()

    tokens, errors = tokenize(source)

    print(f"{'LINE':<6}{'COL':<5}{'TYPE':<12}VALUE")
    for tok in tokens:
        print(f"{tok.line:<6}{tok.column:<5}{tok.type:<12}{tok.value}")

    print()
    if errors:
        for err in errors:
            print(err)
    else:
        print("No lexical errors")
