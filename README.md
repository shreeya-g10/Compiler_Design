# CREF-Lang Simplified

A small Compiler Design college project: a mini language for writing **cascade risks**
(how one risk, like climate change, spreads to another, like migration) and a simple
compiler that turns them into a graph and analyses it.

> **Credit:** Inspired by the research paper *"CREF-Lang: A domain-specific language and
> compiler for cross-domain cascade-risk notation"* (DOI: [10.1016/j.softx.2026.102861](https://doi.org/10.1016/j.softx.2026.102861)).
> This is a **simplified student version**, not a full reimplementation of the paper.

## The Language

```
# Lines starting with # are comments
FACTOR -> FACTOR                 # basic form
FACTOR ->(fast)[F] FACTOR        # with optional extra info
```

- `(fast)` / `(slow)` – propagation speed
- `[F]` empirical, `[E]` established theory, `[M]` modelled
- One relationship per line

## Install

```bash
# run from the project folder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## How to Run

Run everything from the project folder.

```bash
# Compile a file (shows every compiler phase step by step)
venv/bin/python main.py examples/polycrisis.txt

# Interactive mode: type relationships line by line, empty line to compile
venv/bin/python main.py

# Add --show to also open the graph picture at the end
venv/bin/python main.py examples/polycrisis.txt --show
```

The graph picture is saved in `output/` and named after the input file
(e.g. `output/polycrisis.png`, or `output/interactive.png` in interactive mode).

Each phase can also be run on its own, e.g. `venv/bin/python lexer.py examples/climate.txt`.

## Run the UI

A web interface (built with Streamlit) for demos:

```bash
venv/bin/streamlit run app.py
```

It opens in your browser at http://localhost:8501. In the UI you can:

- load any example from the **Demo templates** dropdown in the sidebar,
- type a program in the **Code editor**, or build lines with the **Relationship builder**
  (pick factors, speed and evidence, then "Add relationship"),
- press **Compile** and look at each phase in its own tab:
  Tokens → Parse / IR → Semantic → Graph → Analysis.

Stop the server with `Ctrl+C` in the terminal.

## Example Files

| File                       | What it shows                                                         |
|----------------------------|-----------------------------------------------------------------------|
| `examples/climate.txt`     | A simple cross-domain cascade: CLIMATE → MIGRATION → CONFLICT         |
| `examples/finance.txt`     | A 4-factor chain that stays inside the Economy domain                 |
| `examples/feedback.txt`    | A feedback loop: MIGRATION ↔ CONFLICT                                 |
| `examples/polycrisis.txt`  | Climate + finance together: a convergence point (FINANCE) and a loop  |
| `examples/semantic.txt`    | Semantic errors and warnings (unknown factor, self-loop, undocumented, mismatch, duplicate) |
| `examples/errors.txt`      | Lexical and syntax errors (compilation fails at lexical analysis)     |

## Pipeline

```
 Source program (.txt)
        │
        ▼
 [1] Lexer          lexer.py          text → tokens
        │
        ▼
 [2] Parser         parser.py         tokens → relationships (IR)
        │
        ▼
 [3] Validator      validator.py      checks meaning using factors.json + evidence_base.json
        │
        ▼
 [4] Graph Builder  graph_builder.py  relationships → NetworkX directed graph
        │
        ▼
 [5] Analyzer       analyzer.py       centrality, convergence, feedback loops,
        │                             triggers, cascade paths
        ▼
 Graph output (output/<name>.png) + analysis report
```

`main.py` is the compiler driver that runs all of these in order.

## Files and Compiler Design Concepts

| File               | Compiler Design concept                         |
|--------------------|-------------------------------------------------|
| `lexer.py`         | Lexical analysis (text → tokens)                |
| `parser.py`        | Syntax analysis (grammar check, builds the IR)  |
| `validator.py`     | Semantic analysis (do factors/evidence exist?)  |
| `factors.json`     | Symbol table (known factors)                    |
| `evidence_base.json` | Reference knowledge used in semantic checks   |
| `graph_builder.py` | Code generation (IR → graph)                    |
| `analyzer.py`      | Analysis / optimisation phase                   |
| `main.py`          | Compiler driver (runs all phases)               |
| `app.py`           | Web UI for the compiler (Streamlit)             |
| `examples/`        | Test input programs (incl. error cases)         |
