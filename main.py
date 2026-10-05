# main.py
# The COMPILER DRIVER: runs the whole pipeline in one command and shows each phase.
#
#   Input -> Lexer -> Parser -> Validator -> Graph Builder -> Analyzer -> Graph Output
#
# Usage:
#   venv/bin/python main.py examples/polycrisis.txt    # compile a file
#   venv/bin/python main.py                            # interactive mode (type it live)
#   add --show to also open the graph picture at the end
#
# main.py only CALLS the other phases and prints their results;
# the real work is done in lexer.py, parser.py, validator.py, graph_builder.py, analyzer.py.

import os
import sys

from lexer import tokenize
from parser import parse
from validator import validate, load_symbol_table
from graph_builder import build_graph, draw_graph, BASE_DIR, OUTPUT_DIR
from analyzer import analyze, print_report

LINE = "=" * 60


# ---------------------------------------------------------------------------
# Small printing helpers
# ---------------------------------------------------------------------------
def header(text):
    print(LINE)
    print(f" {text}")
    print(LINE)


def phase(number, title):
    print(f"\n[{number}] {title}")


def finish(message):
    """Print the final RESULT banner."""
    print()
    header(f"RESULT: {message}")


# ---------------------------------------------------------------------------
# Interactive mode: let the user type a program line by line
# ---------------------------------------------------------------------------
def read_interactive():
    print("CREF-Lang interactive mode")
    print("Syntax:  FACTOR ->(fast|slow)[F|E|M] FACTOR   (speed and evidence are optional)")
    print("Valid factors: " + ", ".join(load_symbol_table()))
    print("Type one relationship per line. Press Enter on an empty line to compile.\n")

    lines = []
    while True:
        try:
            text = input("> ")
        except EOFError:          # input ended (e.g. piped input or Ctrl+D)
            break
        if text.strip() == "":    # empty line ends input
            break
        lines.append(text)
    print()
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The compiler: run every phase and print what it did
# ---------------------------------------------------------------------------
def compile_program(source_text, input_name, png_path):
    """Run all phases. Returns the PNG path if a graph was made, else None."""
    header(f"CREF-Lang Compiler  |  input: {input_name}")

    # ----- [1] Source program -----
    phase(1, "SOURCE PROGRAM")
    for number, text in enumerate(source_text.splitlines(), start=1):
        if text.strip() and not text.strip().startswith("#"):   # skip blanks and comments
            print(f"    {number:>3} | {text}")

    # ----- [2] Lexical analysis -----
    phase(2, "LEXICAL ANALYSIS")
    tokens, lex_errors = tokenize(source_text)
    print(f"    {len(tokens)} tokens (including NEWLINE and EOF)")
    # Group tokens by line for a compact view (NEWLINE/EOF are left out here)
    by_line = {}
    for tok in tokens:
        if tok.type in ("NEWLINE", "EOF"):
            continue
        text = tok.type if tok.type == "ARROW" else f"{tok.type}({tok.value.strip('()[]')})"
        by_line.setdefault(tok.line, []).append(text)
    for number, parts in by_line.items():
        print(f"    line {number}: {' '.join(parts)}")
    if lex_errors:
        for err in lex_errors:
            print(f"    ✗ {err}")
        finish("Compilation failed at lexical analysis")
        return None
    print("    ✓ No lexical errors")

    # ----- [3] Syntax analysis -----
    phase(3, "SYNTAX ANALYSIS")
    relationships, syntax_errors = parse(tokens)
    print("    Intermediate representation (parsed relationships):")
    print(f"    {'LINE':<6}{'SOURCE':<17}{'->':<4}{'DESTINATION':<17}{'SPEED':<7}EVIDENCE")
    for r in relationships:
        print(f"    {r.line:<6}{r.source:<17}{'->':<4}{r.destination:<17}"
              f"{r.speed or '-':<7}{r.evidence or '-'}")
    if syntax_errors:
        for err in syntax_errors:
            print(f"    ✗ {err}")
        finish("Compilation failed at syntax analysis")
        return None
    print(f"    ✓ No syntax errors ({len(relationships)} relationships)")

    # ----- [4] Semantic analysis -----
    phase(4, "SEMANTIC ANALYSIS")
    valid, sem_errors, warnings = validate(relationships)
    for err in sem_errors:
        print(f"    ✗ {err}")
    for warn in warnings:
        print(f"    ⚠ {warn}")
    if not sem_errors and not warnings:
        print("    ✓ No semantic errors or warnings")
    print(f"    {len(valid)} valid relationships "
          f"({len(sem_errors)} errors, {len(warnings)} warnings)")
    if not valid:
        finish("Compilation failed at semantic analysis (no valid relationships)")
        return None

    # ----- [5] Graph generation -----
    phase(5, "GRAPH GENERATION")
    G = build_graph(valid)
    draw_graph(G, f"Cascade graph: {os.path.basename(input_name)}", png_path)
    print(f"    {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"    Graph saved to: {os.path.relpath(png_path, BASE_DIR)}")

    # ----- [6] Analysis -----
    phase(6, "ANALYSIS")
    print_report(analyze(G))

    # ----- Final result -----
    summary = f"{len(valid)} relationships, {len(warnings)} warnings"
    if sem_errors:
        summary += f", {len(sem_errors)} semantic errors removed"
    finish(f"Compilation successful ({summary})")
    return png_path


def show_png(png_path):
    """Open the saved PNG in a window (used by --show)."""
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    # graph_builder.py uses the "Agg" backend (files only), so switch back to
    # matplotlib's normal automatic backend, which can open a window.
    plt.switch_backend(matplotlib.rcParamsOrig["backend"])
    plt.figure(figsize=(10, 7))
    plt.imshow(mpimg.imread(png_path))
    plt.axis("off")
    plt.show()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    show = "--show" in args
    files = [a for a in args if a != "--show"]

    if len(files) > 1:
        print("Usage: python main.py [input_file] [--show]")
        sys.exit(1)

    if files:
        input_name = files[0]
        with open(input_name, encoding="utf-8") as f:
            source_text = f.read()
        png_name = os.path.splitext(os.path.basename(input_name))[0] + ".png"
    else:
        source_text = read_interactive()
        input_name = "interactive"
        png_name = "interactive.png"

    png_path = compile_program(source_text, input_name, os.path.join(OUTPUT_DIR, png_name))

    if png_path is None:
        sys.exit(1)        # compilation failed
    if show:
        show_png(png_path)


if __name__ == "__main__":
    main()
