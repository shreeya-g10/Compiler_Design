# validator.py
# SEMANTIC ANALYSIS: checks the MEANING of each relationship from the parser.
#
# The parser only checks structure ("is it written correctly?").
# The validator checks meaning ("does it make sense?") using two JSON files:
#   - factors.json       -> our SYMBOL TABLE (which factors exist, and their domain)
#   - evidence_base.json -> the list of documented relationships
#
# ERRORS (relationship is rejected):
#   1. Unknown factor  - source or destination is not in factors.json
#   2. Self-loop       - source and destination are the same factor
#
# WARNINGS (relationship is kept, but flagged):
#   3. Not documented  - both factors exist, but the edge is not in the evidence base
#   4. Mismatch        - written speed/evidence differs from the evidence base
#   5. Duplicate       - the same source -> destination was already written
#                        (the first copy is kept, the repeated copy is ignored)

import json
import os
import sys
from dataclasses import dataclass

from lexer import tokenize
from parser import parse


# ---------------------------------------------------------------------------
# 1. Load the JSON files (paths are relative to this file, so it works anywhere)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_symbol_table():
    """Return a dictionary: factor code -> domain, e.g. {"CLIMATE": "Environment", ...}"""
    with open(os.path.join(BASE_DIR, "factors.json"), encoding="utf-8") as f:
        data = json.load(f)
    return {factor["code"]: factor["domain"] for factor in data["factors"]}


def load_evidence_base():
    """Return a dictionary: (source, destination) -> edge info from evidence_base.json"""
    with open(os.path.join(BASE_DIR, "evidence_base.json"), encoding="utf-8") as f:
        data = json.load(f)
    return {(edge["source"], edge["destination"]): edge for edge in data["edges"]}


# ---------------------------------------------------------------------------
# 2. The output: a relationship enriched with information from the JSON files
# ---------------------------------------------------------------------------
@dataclass
class ValidatedRelationship:
    source: str
    destination: str
    speed: str                # "fast"/"slow" (filled from evidence base if left blank)
    evidence: str             # "F"/"E"/"M"   (filled from evidence base if left blank)
    line: int
    source_domain: str        # e.g. "Environment"
    destination_domain: str   # e.g. "Society"
    mechanism: str            # e.g. "shock", or "unknown" if undocumented
    documented: bool          # True if found in evidence_base.json


# ---------------------------------------------------------------------------
# 3. The validate function
# ---------------------------------------------------------------------------
def validate(relationships):
    """Check every relationship. Returns (valid_relationships, errors, warnings)."""
    symbol_table = load_symbol_table()
    evidence_base = load_evidence_base()

    valid = []
    errors = []
    warnings = []
    seen = set()   # (source, destination) pairs we have already accepted

    for r in relationships:
        edge_name = f"{r.source} -> {r.destination}"

        # ----- Check 1: unknown factors (ERROR) -----
        unknown = False
        for factor in (r.source, r.destination):
            if factor not in symbol_table:
                errors.append(f"Semantic error at line {r.line}: unknown factor '{factor}'")
                unknown = True
        if unknown:
            continue   # reject this relationship

        # ----- Check 2: self-loop (ERROR) -----
        if r.source == r.destination:
            errors.append(f"Semantic error at line {r.line}: self-loop '{edge_name}' "
                          f"(a factor cannot cascade into itself)")
            continue   # reject this relationship

        # ----- Check 5: duplicate (WARNING) -----
        key = (r.source, r.destination)
        if key in seen:
            warnings.append(f"Warning at line {r.line}: {edge_name} is a duplicate "
                            f"(already written earlier, ignoring this copy)")
            continue   # keep only the first copy
        seen.add(key)

        # Start with what the user wrote
        speed = r.speed
        evidence = r.evidence
        documented = key in evidence_base

        if not documented:
            # ----- Check 3: not documented (WARNING) -----
            warnings.append(f"Warning at line {r.line}: {edge_name} is not in the "
                            f"evidence base (undocumented relationship)")
            mechanism = "unknown"
        else:
            known = evidence_base[key]
            mechanism = known["mechanism"]

            # ----- Check 4: mismatch with the evidence base (WARNING) -----
            if speed is not None and speed != known["velocity"]:
                warnings.append(f"Warning at line {r.line}: {edge_name} written as "
                                f"({speed}) but evidence base says ({known['velocity']})")
            if evidence is not None and evidence != known["evidence"]:
                warnings.append(f"Warning at line {r.line}: {edge_name} written as "
                                f"[{evidence}] but evidence base says [{known['evidence']}]")

            # Fill in anything the user left blank
            if speed is None:
                speed = known["velocity"]
            if evidence is None:
                evidence = known["evidence"]

        valid.append(ValidatedRelationship(
            source=r.source,
            destination=r.destination,
            speed=speed,
            evidence=evidence,
            line=r.line,
            source_domain=symbol_table[r.source],
            destination_domain=symbol_table[r.destination],
            mechanism=mechanism,
            documented=documented,
        ))

    return valid, errors, warnings


# ---------------------------------------------------------------------------
# 4. Demo: venv/bin/python validator.py examples/climate.txt
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validator.py <input_file>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        source_text = f.read()

    # Phase 1 and 2: lexer and parser. Stop if either finds errors.
    tokens, lex_errors = tokenize(source_text)
    relationships, syntax_errors = parse(tokens)
    if lex_errors or syntax_errors:
        for err in lex_errors + syntax_errors:
            print(err)
        print("\nStopped: fix the lexical/syntax errors above before semantic analysis.")
        sys.exit(1)

    # Phase 3: semantic analysis
    valid, errors, warnings = validate(relationships)

    print(f"{'LINE':<6}{'SOURCE (domain)':<27}{'->':<4}{'DESTINATION (domain)':<27}"
          f"{'SPEED':<7}{'EVID':<6}{'MECHANISM':<17}DOCUMENTED")
    for v in valid:
        src = f"{v.source} ({v.source_domain})"
        dst = f"{v.destination} ({v.destination_domain})"
        print(f"{v.line:<6}{src:<27}{'->':<4}{dst:<27}"
              f"{v.speed or '-':<7}{v.evidence or '-':<6}{v.mechanism:<17}"
              f"{'yes' if v.documented else 'no'}")

    print()
    if errors:
        for err in errors:
            print(err)
    else:
        print("No semantic errors")
    for warn in warnings:
        print(warn)
