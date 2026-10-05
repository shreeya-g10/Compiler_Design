# analyzer.py
# ANALYSIS: studies the compiled cascade graph and reports
#   1. CENTRALITY     - which factor is the most connected / influential
#   2. CONVERGENCE    - factors where several pathways meet (in-degree >= 2)
#   3. FEEDBACK LOOPS - cycles, where a risk comes back and feeds itself
#   4. TRIGGERS       - factors nothing points to (in-degree 0): cascades start here
#   5. CASCADE PATHS  - the longest chain from each trigger, and how many domains it crosses

import os
import sys

import networkx as nx

from lexer import tokenize
from parser import parse
from validator import validate
from graph_builder import build_graph, draw_graph, BASE_DIR, OUTPUT_DIR


# ---------------------------------------------------------------------------
# 1. The analyze function
# ---------------------------------------------------------------------------
def analyze(G):
    """Analyze a cascade graph. Returns a dictionary of results."""
    results = {}

    # ----- 1. CENTRALITY -----
    # degree_centrality = (in-degree + out-degree) / (number of other nodes)
    # In a directed graph this can be above 1, because incoming AND outgoing
    # edges both count (e.g. 2 factors pointing at each other give 2 / 1 = 2.0).
    centrality = nx.degree_centrality(G)
    table = []
    for node in G.nodes:
        table.append({
            "factor": node,
            "centrality": centrality[node],
            "out_degree": G.out_degree(node),   # how many factors it affects
            "in_degree": G.in_degree(node),     # how many factors affect it
        })
    table.sort(key=lambda row: row["centrality"], reverse=True)   # highest first
    results["centrality"] = table

    # The top factor(s): there may be a tie
    top_score = table[0]["centrality"] if table else 0
    results["most_central"] = [row for row in table if row["centrality"] == top_score]

    # ----- 2. CONVERGENCE: nodes with 2 or more incoming edges -----
    results["convergence"] = [
        {"factor": node, "from": sorted(G.predecessors(node))}
        for node in G.nodes if G.in_degree(node) >= 2
    ]

    # ----- 3. FEEDBACK LOOPS: cycles in the graph -----
    # Each loop is rotated to start at the factor that appears first in the program,
    # so MIGRATION -> CONFLICT is printed in the same order the user wrote it.
    node_order = list(G.nodes)
    loops = []
    for cycle in nx.simple_cycles(G):
        start = cycle.index(min(cycle, key=node_order.index))
        loops.append(cycle[start:] + cycle[:start])
    results["feedback_loops"] = loops

    # ----- 4. TRIGGERS: nodes with no incoming edges -----
    triggers = [node for node in G.nodes if G.in_degree(node) == 0]
    results["triggers"] = triggers

    # ----- 5. CASCADE PATHS: longest simple path from each trigger -----
    cascade_paths = []
    for trigger in triggers:
        best_path = [trigger]
        for target in G.nodes:
            if target == trigger:
                continue
            for path in nx.all_simple_paths(G, trigger, target):
                # Prefer longer paths; if equal length, prefer the one crossing more domains
                if (len(path), count_domains(G, path)) > (len(best_path), count_domains(G, best_path)):
                    best_path = path
        cascade_paths.append({
            "trigger": trigger,
            "path": best_path,
            "domains": [G.nodes[n]["domain"] for n in best_path],
            "num_domains": count_domains(G, best_path),
        })
    results["cascade_paths"] = cascade_paths

    return results


def count_domains(G, path):
    """How many DIFFERENT domains the factors on this path belong to."""
    return len({G.nodes[n]["domain"] for n in path})


# ---------------------------------------------------------------------------
# 2. Print a neat report
# ---------------------------------------------------------------------------
def print_report(results):
    print("=== CENTRALITY ===")
    print(f"{'FACTOR':<17}{'CENTRALITY':<12}{'AFFECTS':<9}AFFECTED BY")
    for row in results["centrality"]:
        print(f"{row['factor']:<17}{row['centrality']:<12.2f}{row['out_degree']:<9}{row['in_degree']}")
    for row in results["most_central"]:
        print(f"Most central factor: {row['factor']} (affects {row['out_degree']}, "
              f"affected by {row['in_degree']})")

    print("\n=== CONVERGENCE ===")
    if results["convergence"]:
        for c in results["convergence"]:
            print(f"{c['factor']}: {len(c['from'])} incoming pathways (from {', '.join(c['from'])})")
    else:
        print("No convergence points")

    print("\n=== FEEDBACK LOOPS ===")
    if results["feedback_loops"]:
        for loop in results["feedback_loops"]:
            print(" → ".join(loop + [loop[0]]))   # close the loop back to its start
    else:
        print("No feedback loops found")

    print("\n=== TRIGGERS ===")
    if results["triggers"]:
        print("Cascades start at: " + ", ".join(results["triggers"]))
    else:
        print("No triggers found (every factor is affected by another one)")

    print("\n=== CASCADE PATHS ===")
    if results["cascade_paths"]:
        for c in results["cascade_paths"]:
            path_text = " → ".join(c["path"])
            if c["num_domains"] == 1:
                # The whole path is in one domain, e.g. all Economy
                print(f"{path_text}  (stays within 1 domain: {c['domains'][0]})")
            else:
                print(f"{path_text}  (crosses {c['num_domains']} domains: "
                      f"{' → '.join(c['domains'])})")
    else:
        print("No cascade paths (no triggers to start from)")


# ---------------------------------------------------------------------------
# 3. Demo: venv/bin/python analyzer.py examples/polycrisis.txt
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyzer.py <input_file>")
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
        print("\nStopped: fix the lexical/syntax errors above before analysis.")
        sys.exit(1)

    # Phase 3: semantic errors only remove bad relationships
    valid, sem_errors, warnings = validate(relationships)
    for msg in sem_errors + warnings:
        print(msg)
    if sem_errors or warnings:
        print()

    # Phase 4: build and save the graph
    G = build_graph(valid)
    name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(OUTPUT_DIR, f"{name}.png")
    draw_graph(G, f"Cascade graph: {name}.txt", output_path)
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges "
          f"(saved to {os.path.relpath(output_path, BASE_DIR)})\n")

    # Phase 5: analysis
    print_report(analyze(G))
