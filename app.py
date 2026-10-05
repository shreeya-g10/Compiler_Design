# app.py
# WEB UI for the CREF-Lang compiler, built with Streamlit.
#
# Run with:  venv/bin/streamlit run app.py
#
# The UI does no compiling itself. It calls the same functions as main.py:
#   tokenize -> parse -> validate -> build_graph / draw_graph -> analyze
# and shows the result of each phase.
#
# Page layout:
#   1. Header + "Try an example" template buttons
#   2. Input: code editor (left) and relationship builder (right), Compile button
#   3. Result: status banner + phase progress
#   4. Cascade graph (interactive, drawn in the browser) + readable relationship list
#   5. Key findings (metric cards)
#   6. Compiler phases in detail (tokens, IR, semantic, analysis, static PNG)

import html
import json
import os

import streamlit as st

from lexer import tokenize
from parser import parse
from validator import validate, load_symbol_table
from graph_builder import build_graph, draw_graph, BASE_DIR, OUTPUT_DIR, DOMAIN_COLOURS
from analyzer import analyze

EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
UI_GRAPH_PATH = os.path.join(OUTPUT_DIR, "ui_graph.png")

# Demo templates: label shown on the button -> file in examples/
TEMPLATES = {
    "🌍 Polycrisis": "polycrisis.txt",
    "🌡️ Climate cascade": "climate.txt",
    "💰 Financial chain": "finance.txt",
    "🔁 Feedback loop": "feedback.txt",
    "⚠️ Semantic errors": "semantic.txt",
    "❌ Syntax errors": "errors.txt",
}
DEFAULT_TEMPLATE = "🌍 Polycrisis"
NOT_SPECIFIED = "not specified"
SKIPPED_MESSAGE = "Skipped: fix the errors above first."

EVIDENCE_NAMES = {"F": "Empirical", "E": "Established theory", "M": "Modelled"}
LOOP_COLOUR = "#C084FC"        # purple: edges that are part of a feedback loop
UNDOCUMENTED_COLOUR = "#F87171"  # red: relationships not in the evidence base


# ---------------------------------------------------------------------------
# 1. Helpers
# ---------------------------------------------------------------------------
def read_template(label):
    """Read an example file. Returns its text, or a comment if it cannot be read."""
    try:
        with open(os.path.join(EXAMPLES_DIR, TEMPLATES[label]), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return f"# Could not read examples/{TEMPLATES[label]}\n"


def load_factor_names():
    """factor code -> full name (e.g. CLIMATE -> Climate Change), from factors.json."""
    with open(os.path.join(BASE_DIR, "factors.json"), encoding="utf-8") as f:
        return {fac["code"]: fac["name"] for fac in json.load(f)["factors"]}


def make_line(source, destination, speed, evidence):
    """Generate one correct CREF-Lang line from the builder's choices."""
    line = f"{source} ->"
    if speed != NOT_SPECIFIED:
        line += f"({speed})"
    if evidence != NOT_SPECIFIED:
        line += f"[{evidence}]"
    return f"{line} {destination}"


def describe(v):
    """Explain one validated relationship in plain English."""
    src, dst = factor_names.get(v.source, v.source), factor_names.get(v.destination, v.destination)
    speed = {"fast": "spreads quickly", "slow": "spreads slowly"}.get(v.speed, "spreads")
    text = f"{src} {speed} into {dst}"
    if v.evidence:
        text += f", backed by {EVIDENCE_NAMES[v.evidence].lower()} evidence"
    return text + "."


def run_compiler(source_text):
    """Run every compiler phase and collect the results in one dictionary.

    'failed_at' is None if compilation succeeded, otherwise the name of the
    phase that stopped it. Later phases are left as None when skipped.
    """
    result = {"failed_at": None, "relationships": None, "syntax_errors": None,
              "valid": None, "sem_errors": None, "warnings": None,
              "graph": None, "png": None, "analysis": None}

    # Phase 1: lexical analysis
    tokens, lex_errors = tokenize(source_text)
    result["tokens"], result["lex_errors"] = tokens, lex_errors
    if lex_errors:
        result["failed_at"] = "lexical analysis"
        return result

    # Phase 2: syntax analysis
    relationships, syntax_errors = parse(tokens)
    result["relationships"], result["syntax_errors"] = relationships, syntax_errors
    if syntax_errors:
        result["failed_at"] = "syntax analysis"
        return result

    # Phase 3: semantic analysis (errors only remove the bad relationships)
    valid, sem_errors, warnings = validate(relationships)
    result.update(valid=valid, sem_errors=sem_errors, warnings=warnings)
    if not valid:
        result["failed_at"] = "semantic analysis"
        return result

    # Phase 4: graph generation (the PNG is kept for download)
    G = build_graph(valid)
    draw_graph(G, "Cascade graph", UI_GRAPH_PATH)
    with open(UI_GRAPH_PATH, "rb") as f:
        result["png"] = f.read()
    result["graph"] = G

    # Phase 5: analysis
    result["analysis"] = analyze(G)
    return result


def to_dot(G, analysis):
    """Turn the compiled graph into Graphviz DOT text, drawn by the browser.

    Left-to-right layout so a cascade reads like a sentence. The analysis is
    shown on the picture too: triggers get a thick border, convergence points
    a double border, and feedback-loop edges are purple.
    """
    triggers = set(analysis["triggers"])
    convergence = {c["factor"] for c in analysis["convergence"]}
    loop_edges = set()
    for loop in analysis["feedback_loops"]:
        for a, b in zip(loop, loop[1:] + loop[:1]):
            loop_edges.add((a, b))

    lines = [
        "digraph G {",
        '  rankdir=LR; bgcolor="transparent"; nodesep=0.45; ranksep=0.8; pad=0.2;',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=16,'
        ' color="#0F1117", fontcolor="#111827", penwidth=1.2, margin="0.25,0.12"];',
        '  edge [fontname="Helvetica bold", fontsize=15, color="#9CA3AF", arrowsize=0.9, penwidth=1.6];',
    ]
    for n in G.nodes:
        colour = DOMAIN_COLOURS.get(G.nodes[n]["domain"], "#E5E7EB")
        name = factor_names.get(n, "")
        extra = ""
        if n in triggers:
            extra += ", penwidth=3"
        if n in convergence:
            extra += ", peripheries=2"
        lines.append(f'  "{n}" [label="{n}\\n{name}", fillcolor="{colour}"{extra}];')
    for a, b, d in G.edges(data=True):
        style = {"fast": "solid", "slow": "dashed"}.get(d.get("speed"), "dotted")
        colour = "#CBD5E1"
        if (a, b) in loop_edges:
            colour = LOOP_COLOUR
        if not d.get("documented"):
            colour = UNDOCUMENTED_COLOUR
        label = d.get("evidence") or "?"
        lines.append(f'  "{a}" -> "{b}" [label=" {label} ", style={style}, color="{colour}",'
                     f' fontcolor="{colour}"];')
    lines.append("}")
    return "\n".join(lines)


def chip(text, colour, outline=False):
    """Small rounded label (HTML)."""
    if outline:
        return f'<span class="chip" style="border-color:{colour};color:{colour}">{html.escape(text)}</span>'
    return f'<span class="chip" style="background:{colour};border-color:{colour}">{html.escape(text)}</span>'


# ---------------------------------------------------------------------------
# 2. Button callbacks (they run BEFORE the page is redrawn, so they are
#    allowed to change the editor text stored in st.session_state)
# ---------------------------------------------------------------------------
def load_template():
    choice = st.session_state.template_choice
    if choice:
        st.session_state.code = read_template(choice)
        compile_code()          # show the graph straight away


def add_relationship():
    line = make_line(st.session_state.b_source, st.session_state.b_destination,
                     st.session_state.b_speed, st.session_state.b_evidence)
    code = st.session_state.code
    if code and not code.endswith("\n"):
        code += "\n"
    st.session_state.code = code + line + "\n"


def clear_editor():
    st.session_state.code = ""
    st.session_state.result = None
    st.session_state.template_choice = None


def compile_code():
    if not st.session_state.code.strip():
        st.session_state.result = {"empty": True}
        return
    try:
        st.session_state.result = run_compiler(st.session_state.code)
    except Exception:
        # Never show a Python traceback in the UI
        st.session_state.result = {"crashed": True}


# ---------------------------------------------------------------------------
# 3. Page setup and styling
# ---------------------------------------------------------------------------
st.set_page_config(page_title="CREF-Lang Compiler", page_icon="🔗", layout="wide")

st.markdown("""
<style>
  .block-container { padding-top: 1.6rem; max-width: 1350px; }
  .hero { background: linear-gradient(120deg, #4F46E5 0%, #7C3AED 55%, #DB2777 100%);
          color: white; border-radius: 16px; padding: 22px 28px; margin-bottom: 18px; }
  .hero h1 { color: white; font-size: 2rem; margin: 0 0 4px; padding: 0; }
  .hero p  { margin: 0 0 14px; opacity: 0.92; }
  .pipeline { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .pipeline .step { padding: 4px 12px; border-radius: 14px; font-size: 0.82rem; font-weight: 600;
                    background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.45); }
  .pipeline .arrow { opacity: 0.75; }
  .section-title { font-size: 1.25rem; font-weight: 700; margin: 6px 0 2px; }
  .section-sub { color: #9CA3AF; font-size: 0.9rem; margin-bottom: 10px; }
  .phase-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 4px; }
  .phase-box { flex: 1; min-width: 120px; text-align: center; padding: 9px 4px; border-radius: 10px;
               font-weight: 600; font-size: 0.9rem; border: 1px solid #374151; background: #1A1D29; }
  .phase-box.ok      { background: rgba(16,185,129,0.12); border-color: #10B981; color: #6EE7B7; }
  .phase-box.warn    { background: rgba(245,158,11,0.12); border-color: #F59E0B; color: #FCD34D; }
  .phase-box.fail    { background: rgba(239,68,68,0.12); border-color: #EF4444; color: #FCA5A5; }
  .phase-box.skipped { color: #6B7280; background: transparent; }
  .chip { display: inline-block; padding: 2px 9px; margin: 2px 4px 2px 0; border-radius: 12px;
          font-size: 0.75rem; font-weight: 600; border: 1px solid; color: #1F2937; white-space: nowrap; }
  .rel-card { background: #1A1D29; border: 1px solid #2D3142; border-left: 4px solid #818CF8;
              border-radius: 10px; padding: 9px 12px; margin-bottom: 8px; }
  .rel-card.undoc { border-left-color: #F87171; }
  .rel-card .flow { font-family: Menlo, monospace; font-weight: 700; font-size: 0.92rem; }
  .rel-card .flow .arr { color: #C084FC; margin: 0 6px; }
  .rel-card .desc { color: #9CA3AF; font-size: 0.85rem; margin: 3px 0 4px; }
  .legend { font-size: 0.82rem; color: #D1D5DB; line-height: 1.9; }
  .legend .sw { display: inline-block; width: 12px; height: 12px; border-radius: 3px;
                margin: 0 4px -1px 10px; border: 1px solid #1F2937; }
  .legend .ln { display: inline-block; width: 26px; margin: 0 4px 3px 10px; border-top: 2px solid #CBD5E1; }
  .stTextArea textarea { font-family: Menlo, "Source Code Pro", monospace; font-size: 0.9rem; }
  [data-testid="stAppDeployButton"], [data-testid="stSkillsNudge"] { display: none; }
  [data-testid="stMetric"] { background: #1A1D29; border: 1px solid #2D3142; border-radius: 12px;
                             padding: 12px 16px; }
</style>
""", unsafe_allow_html=True)

# Session state: remembered between button clicks
if "code" not in st.session_state:
    st.session_state.code = read_template(DEFAULT_TEMPLATE)
if "result" not in st.session_state:
    compile_code()              # first visit: compile the default example immediately
if "template_choice" not in st.session_state:
    st.session_state.template_choice = DEFAULT_TEMPLATE

symbol_table = load_symbol_table()     # factor code -> domain (from factors.json)
factor_names = load_factor_names()     # factor code -> full name
factor_codes = list(symbol_table)


# ---------------------------------------------------------------------------
# 4. Header
# ---------------------------------------------------------------------------
steps = ["Source", "Lexer", "Parser", "Validator", "Graph", "Analysis"]
st.markdown(
    '<div class="hero"><h1>🔗 CREF-Lang Compiler</h1>'
    "<p>A simplified compiler for cross-domain cascade-risk notation "
    "(based on Undheim, <i>SoftwareX</i> 2026)</p>"
    '<div class="pipeline">'
    + '<span class="arrow">→</span>'.join(f'<span class="step">{s}</span>' for s in steps)
    + "</div></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 5. Sidebar: syntax help and known factors
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("📘 Syntax")
    st.code("A ->(speed)[evidence] B", language=None)
    st.markdown("- **(fast)** / **(slow)**: how quickly the risk spreads\n"
                "- **[F]** empirical · **[E]** established theory · **[M]** modelled\n"
                "- Speed and evidence are optional\n"
                "- One relationship per line, `#` starts a comment")
    st.caption("Example:")
    st.code("CLIMATE ->(fast)[F] MIGRATION", language=None)

    st.header("🧩 Known factors")
    by_domain = {}
    for code, domain in symbol_table.items():
        by_domain.setdefault(domain, []).append(code)
    for domain, codes in by_domain.items():
        colour = DOMAIN_COLOURS.get(domain, "#E5E7EB")
        st.markdown(f"**{domain}**<br>" + "".join(chip(c, colour) for c in codes),
                    unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 6. Input: templates, code editor (left) and relationship builder (right)
# ---------------------------------------------------------------------------
st.pills("**Try an example:**", list(TEMPLATES), key="template_choice", on_change=load_template)

editor_col, builder_col = st.columns([3, 2], gap="large")

with editor_col:
    with st.container(border=True):
        st.markdown('<div class="section-title">✍️ Write CREF-Lang</div>'
                    '<div class="section-sub">One relationship per line. Lines starting with # are comments.</div>',
                    unsafe_allow_html=True)
        st.text_area("CREF-Lang program", key="code", height=300, label_visibility="collapsed")

with builder_col:
    with st.container(border=True):
        st.markdown('<div class="section-title">🧱 Relationship builder</div>'
                    '<div class="section-sub">No need to know the syntax: pick the details '
                    'and the line is generated for you.</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.selectbox("Source factor", factor_codes, key="b_source",
                     format_func=lambda c: f"{c} ({symbol_table[c]})")
        c2.selectbox("Destination factor", factor_codes, index=1, key="b_destination",
                     format_func=lambda c: f"{c} ({symbol_table[c]})")
        c3, c4 = st.columns(2)
        c3.selectbox("Speed", [NOT_SPECIFIED, "fast", "slow"], key="b_speed")
        c4.selectbox("Evidence", [NOT_SPECIFIED, "F", "E", "M"], key="b_evidence",
                     format_func=lambda e: f"{e} ({EVIDENCE_NAMES[e]})" if e in EVIDENCE_NAMES else e)
        st.caption("Generated line:")
        st.code(make_line(st.session_state.b_source, st.session_state.b_destination,
                          st.session_state.b_speed, st.session_state.b_evidence), language=None)
        b1, b2 = st.columns(2)
        b1.button("➕ Add to program", on_click=add_relationship, width="stretch")
        b2.button("🗑 Clear editor", on_click=clear_editor, width="stretch")

st.button("▶  Compile", type="primary", on_click=compile_code, width="stretch")


# ---------------------------------------------------------------------------
# 7. Result: status banner + phase progress
# ---------------------------------------------------------------------------
result = st.session_state.result

if result is None:
    st.info("👆 Pick an example or write your own relationships, then press **Compile** "
            "to see the relationship graph and analysis.")
    st.stop()
if result.get("empty"):
    st.warning("The editor is empty. Load an example or add a relationship first.")
    st.stop()
if result.get("crashed"):
    st.error("Something unexpected went wrong while compiling. Please check the program and try again.")
    st.stop()

st.divider()

if result["failed_at"]:
    st.error(f"**✗ Compilation failed at {result['failed_at']}.** See the errors below.")
else:
    st.success(f"**✓ Compilation successful**: {len(result['valid'])} relationships, "
               f"{len(result['warnings'])} warnings")


def phase_status():
    """Return (name, css class, icon) for each of the 5 phases."""
    lex_ok = not result["lex_errors"]
    syn_ok = lex_ok and not result["syntax_errors"]
    statuses = [("Lexer", "ok" if lex_ok else "fail")]
    statuses.append(("Parser", "skipped" if not lex_ok else ("ok" if syn_ok else "fail")))
    if not syn_ok:
        sem = "skipped"
    elif not result["valid"]:
        sem = "fail"
    elif result["sem_errors"] or result["warnings"]:
        sem = "warn"
    else:
        sem = "ok"
    statuses.append(("Validator", sem))
    later = "ok" if result["analysis"] else "skipped"
    statuses += [("Graph", later), ("Analysis", later)]
    icons = {"ok": "✓", "warn": "⚠", "fail": "✗", "skipped": "–"}
    return [(name, css, icons[css]) for name, css in statuses]


st.markdown('<div class="phase-row">' + "".join(
    f'<div class="phase-box {css}">{icon} {name}{" (skipped)" if css == "skipped" else ""}</div>'
    for name, css, icon in phase_status()) + "</div>", unsafe_allow_html=True)

# If compilation failed, show the errors right here so they're impossible to miss
if result["failed_at"]:
    errors = result["lex_errors"] or result["syntax_errors"] or result["sem_errors"] or []
    st.error("\n".join(f"- {e}" for e in errors))
else:
    # Compiled, but the validator removed or flagged some relationships
    if result["sem_errors"]:
        st.error("**Removed by the validator:**\n" + "\n".join(f"- {e}" for e in result["sem_errors"]))
    if result["warnings"]:
        st.warning("**Warnings (kept):**\n" + "\n".join(f"- {w}" for w in result["warnings"]))


# ---------------------------------------------------------------------------
# 8. Cascade graph + relationship list (the main output)
# ---------------------------------------------------------------------------
a = result["analysis"]
if a is not None:
    G = result["graph"]
    st.write("")
    with st.container(border=True):
        st.markdown(f'<div class="section-title">🕸️ Cascade relationship graph</div>'
                    f'<div class="section-sub">{G.number_of_nodes()} factors · '
                    f'{G.number_of_edges()} relationships · read left to right</div>',
                    unsafe_allow_html=True)
        st.graphviz_chart(to_dot(G, a), width="stretch")
        domains_used = sorted({G.nodes[n]["domain"] for n in G.nodes})
        st.markdown(
            '<div class="legend">'
            + "".join(f'<span class="sw" style="background:{DOMAIN_COLOURS.get(d, "#E5E7EB")}"></span>{d}'
                      for d in domains_used)
            + '&nbsp;&nbsp;|'
            '<span class="ln"></span>fast'
            '<span class="ln" style="border-top-style:dashed"></span>slow'
            '<span class="ln" style="border-top-style:dotted"></span>unknown speed'
            f'<span class="ln" style="border-top-color:{LOOP_COLOUR}"></span>feedback loop'
            f'<span class="ln" style="border-top-color:{UNDOCUMENTED_COLOUR}"></span>undocumented'
            "<br>&nbsp;&nbsp;&nbsp;Edge label = evidence (F/E/M) · thick border = trigger "
            "(where a cascade starts) · double border = convergence point"
            "</div>", unsafe_allow_html=True)

    # ----- Relationship cards, 3 per row -----
    st.write("")
    st.markdown('<div class="section-title">🔗 Relationships</div>'
                '<div class="section-sub">What the compiler understood, in plain English</div>',
                unsafe_allow_html=True)
    card_cols = st.columns(3)
    for i, v in enumerate(result["valid"]):
        chips = ""
        if v.speed:
            chips += chip(v.speed, "#C7D2FE")
        if v.evidence:
            chips += chip(EVIDENCE_NAMES[v.evidence], "#FCE7F3")
        chips += chip(v.mechanism.replace("_", " "), "#F3F4F6")
        chips += (chip("✓ documented", "#34D399", outline=True) if v.documented
                  else chip("⚠ undocumented", UNDOCUMENTED_COLOUR, outline=True))
        card_cols[i % 3].markdown(
            f'<div class="rel-card{"" if v.documented else " undoc"}">'
            f'<div class="flow">{html.escape(v.source)}<span class="arr">⟶</span>'
            f'{html.escape(v.destination)}</div>'
            f'<div class="desc">{html.escape(describe(v))}</div>{chips}</div>',
            unsafe_allow_html=True)

    # ----- Key findings -----
    st.write("")
    st.markdown('<div class="section-title">📊 Key findings</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Most central factor", ", ".join(r["factor"] for r in a["most_central"]))
    m2.metric("Convergence points", len(a["convergence"]),
              help=", ".join(c["factor"] for c in a["convergence"]) or "none")
    m3.metric("Feedback loops", len(a["feedback_loops"]))
    m4.metric("Triggers (start points)", len(a["triggers"]),
              help=", ".join(a["triggers"]) or "none")

    for c in a["cascade_paths"]:
        path = " → ".join(c["path"])
        if c["num_domains"] == 1:
            st.markdown(f"🛤️ **{path}**: stays within 1 domain ({c['domains'][0]})")
        else:
            st.markdown(f"🛤️ **{path}**: crosses **{c['num_domains']} domains** "
                        f"({' → '.join(c['domains'])})")


# ---------------------------------------------------------------------------
# 9. Compiler phases in detail
# ---------------------------------------------------------------------------
st.write("")
st.markdown('<div class="section-title">⚙️ Compiler phases in detail</div>'
            '<div class="section-sub">What each phase of the compiler produced</div>',
            unsafe_allow_html=True)
tab_tokens, tab_ir, tab_sem, tab_analysis, tab_png = st.tabs(
    ["1. Lexer: tokens", "2. Parser: IR", "3. Validator: semantics",
     "4. Analysis: details", "5. Static graph (PNG)"])

# ----- Tab 1: tokens -----
with tab_tokens:
    if result["lex_errors"]:
        st.error("**Lexical errors**\n\n" + "\n".join(f"- {e}" for e in result["lex_errors"]))
    else:
        st.success("No lexical errors")
    st.caption(f"{len(result['tokens'])} tokens (including NEWLINE and EOF)")
    # NEWLINE/EOF rows are hidden by default so the real tokens are easy to see
    show_all = st.toggle("Show NEWLINE and EOF tokens", value=False)
    st.dataframe([{"Line": t.line, "Column": t.column, "Type": t.type, "Value": t.value}
                  for t in result["tokens"]
                  if show_all or t.type not in ("NEWLINE", "EOF")],
                 hide_index=True, width="stretch")

# ----- Tab 2: parse / IR -----
with tab_ir:
    if result["relationships"] is None:
        st.info(SKIPPED_MESSAGE)
    else:
        if result["syntax_errors"]:
            st.error("**Syntax errors**\n\n" + "\n".join(f"- {e}" for e in result["syntax_errors"]))
        else:
            st.success("No syntax errors")
        st.caption("Intermediate representation: one Relationship per valid line")
        st.dataframe([{"Line": r.line, "Source": r.source, "Destination": r.destination,
                       "Speed": r.speed or "-", "Evidence": r.evidence or "-"}
                      for r in result["relationships"]], hide_index=True, width="stretch")

# ----- Tab 3: semantic -----
with tab_sem:
    if result["valid"] is None:
        st.info(SKIPPED_MESSAGE)
    else:
        if result["sem_errors"]:
            st.error("**Semantic errors** (these relationships were removed)\n\n"
                     + "\n".join(f"- {e}" for e in result["sem_errors"]))
        if result["warnings"]:
            st.warning("**Warnings** (these relationships were kept)\n\n"
                       + "\n".join(f"- {w}" for w in result["warnings"]))
        if not result["sem_errors"] and not result["warnings"]:
            st.success("No semantic errors or warnings")
        st.caption(f"{len(result['valid'])} validated relationships")
        st.dataframe([{"Line": v.line,
                       "Source": f"{v.source} ({v.source_domain})",
                       "Destination": f"{v.destination} ({v.destination_domain})",
                       "Speed": v.speed or "-", "Evidence": v.evidence or "-",
                       "Mechanism": v.mechanism,
                       "Documented": "yes" if v.documented else "no"}
                      for v in result["valid"]], hide_index=True, width="stretch")

# ----- Tab 4: analysis details -----
with tab_analysis:
    if a is None:
        st.info(SKIPPED_MESSAGE)
    else:
        st.subheader("Centrality")
        st.caption("How connected each factor is (affects = outgoing edges, affected by = incoming edges)")
        st.dataframe([{"Factor": r["factor"], "Centrality": round(r["centrality"], 2),
                       "Affects": r["out_degree"], "Affected by": r["in_degree"]}
                      for r in a["centrality"]], hide_index=True, width="stretch")

        st.subheader("Convergence points")
        if a["convergence"]:
            for c in a["convergence"]:
                st.markdown(f"- **{c['factor']}**: {len(c['from'])} incoming pathways "
                            f"(from {', '.join(c['from'])})")
        else:
            st.markdown("No convergence points")

        st.subheader("Feedback loops")
        if a["feedback_loops"]:
            for loop in a["feedback_loops"]:
                st.markdown("- " + " → ".join(loop + [loop[0]]))
        else:
            st.markdown("No feedback loops found")

        st.subheader("Triggers")
        if a["triggers"]:
            st.markdown("Cascades start at: **" + "**, **".join(a["triggers"]) + "**")
        else:
            st.markdown("No triggers found (every factor is affected by another one)")

# ----- Tab 5: static PNG from graph_builder.py -----
with tab_png:
    if result["png"] is None:
        st.info(SKIPPED_MESSAGE)
    else:
        st.caption("The same graph drawn by graph_builder.py with NetworkX + Matplotlib")
        st.image(result["png"], width=850)
        st.download_button("⬇ Download graph (PNG)", result["png"],
                           file_name="cref_graph.png", mime="image/png")
