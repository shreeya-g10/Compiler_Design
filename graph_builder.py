# graph_builder.py
# CODE GENERATION: turns the validated relationships (our IR) into a
# NetworkX directed graph - the "compiled" output of a CREF-Lang program.
#
#   - each factor       -> a NODE  (attribute: domain)
#   - each relationship -> an EDGE (attributes: speed, evidence, mechanism, documented, line)
#
# It can also draw the graph as a PNG picture using matplotlib.

import os
import sys

import matplotlib
matplotlib.use("Agg")   # draw to a file only, no pop-up window
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import networkx as nx

from lexer import tokenize
from parser import parse
from validator import validate


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# One colour per domain (used for node colours and the legend)
DOMAIN_COLOURS = {
    "Environment": "#4CAF50",   # green
    "Society":     "#FFB74D",   # orange
    "Governance":  "#9575CD",   # purple
    "Health":      "#F06292",   # pink
    "Economy":     "#64B5F6",   # blue
}


# ---------------------------------------------------------------------------
# 1. Build the graph
# ---------------------------------------------------------------------------
def build_graph(valid_relationships):
    """Turn a list of ValidatedRelationship objects into a directed graph."""
    G = nx.DiGraph()   # directed: a cascade goes FROM one factor TO another

    for r in valid_relationships:
        # Nodes (adding the same node twice is fine - NetworkX keeps one copy)
        G.add_node(r.source, domain=r.source_domain)
        G.add_node(r.destination, domain=r.destination_domain)

        # Edge with all the information about the relationship
        G.add_edge(r.source, r.destination,
                   speed=r.speed,
                   evidence=r.evidence,
                   mechanism=r.mechanism,
                   documented=r.documented,
                   line=r.line)
    return G


# ---------------------------------------------------------------------------
# 2. Draw the graph as a PNG
# ---------------------------------------------------------------------------
def draw_graph(G, title, output_path):
    """Save a picture of the graph to 'output_path'."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 7))

    # Spread the nodes out; a fixed seed gives the same picture every run.
    # Seed 176 was chosen because it gives no edge crossings in our example graphs.
    pos = nx.spring_layout(G, seed=176, k=1.5)

    # --- Nodes: coloured by domain ---
    node_colours = [DOMAIN_COLOURS.get(G.nodes[n]["domain"], "lightgrey") for n in G.nodes]
    nx.draw_networkx_nodes(G, pos, node_color=node_colours, node_size=3000,
                           edgecolors="black", ax=ax)
    # Long names are split at "_" so they fit inside the circle (MONETARY_POLICY -> MONETARY / POLICY)
    node_labels = {n: n.replace("_", "\n") for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8, font_weight="bold", ax=ax)

    # --- Edges: solid = fast, dashed = slow, dotted = unknown speed ---
    #     red = undocumented, black = documented
    # A small curve (rad=0.15) keeps A -> B and B -> A from overlapping.
    curve = "arc3,rad=0.15"
    styles = {"fast": "solid", "slow": "dashed", None: "dotted"}
    for speed, style in styles.items():
        edges = [(u, v) for u, v, d in G.edges(data=True) if d["speed"] == speed]
        colours = ["black" if G.edges[e]["documented"] else "red" for e in edges]
        nx.draw_networkx_edges(G, pos, edgelist=edges, style=style, edge_color=colours,
                               width=2, arrowsize=20, node_size=3000,
                               connectionstyle=curve, ax=ax)

    # --- Edge labels: the evidence tag (F / E / M) ---
    labels = {(u, v): d["evidence"] or "?" for u, v, d in G.edges(data=True)}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=labels, font_size=10,
                                 rotate=False, connectionstyle=curve, ax=ax)

    # --- Legend: domains + edge styles ---
    legend_items = [Patch(facecolor=colour, edgecolor="black", label=domain)
                    for domain, colour in DOMAIN_COLOURS.items()]
    legend_items += [
        Line2D([0], [0], color="black", linestyle="solid", label="fast"),
        Line2D([0], [0], color="black", linestyle="dashed", label="slow"),
        Line2D([0], [0], color="black", linestyle="dotted", label="speed unknown"),
        Line2D([0], [0], color="red", label="undocumented"),
    ]
    ax.legend(handles=legend_items, loc="upper left", bbox_to_anchor=(1, 1),
              title="Legend  (edge label = evidence)")

    ax.set_title(title, fontsize=14)
    ax.margins(0.2)   # leave space so big nodes are not cut off at the edges
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 3. Demo: venv/bin/python graph_builder.py examples/climate.txt
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python graph_builder.py <input_file>")
        sys.exit(1)

    input_path = sys.argv[1]
    with open(input_path, encoding="utf-8") as f:
        source_text = f.read()

    # Phase 1 and 2: stop if there are lexical or syntax errors
    tokens, lex_errors = tokenize(source_text)
    relationships, syntax_errors = parse(tokens)
    if lex_errors or syntax_errors:
        for err in lex_errors + syntax_errors:
            print(err)
        print("\nStopped: fix the lexical/syntax errors above before building the graph.")
        sys.exit(1)

    # Phase 3: semantic errors only remove bad relationships, so we carry on
    valid, sem_errors, warnings = validate(relationships)
    for msg in sem_errors + warnings:
        print(msg)
    if sem_errors or warnings:
        print()

    # Phase 4: build and draw the graph
    G = build_graph(valid)
    print(f"Nodes: {G.number_of_nodes()}   Edges: {G.number_of_edges()}\n")
    for u, v, d in G.edges(data=True):
        print(f"{u + ' -> ' + v:<32}speed={d['speed'] or '-':<6}"
              f"evidence={d['evidence'] or '-':<3}mechanism={d['mechanism']:<17}"
              f"documented={'yes' if d['documented'] else 'no'}")

    name = os.path.splitext(os.path.basename(input_path))[0]   # "climate"
    output_path = os.path.join(OUTPUT_DIR, f"{name}.png")
    draw_graph(G, f"Cascade graph: {name}.txt", output_path)
    print(f"\nGraph saved to: {os.path.relpath(output_path, BASE_DIR)}")
