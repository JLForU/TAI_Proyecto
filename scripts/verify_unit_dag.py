#!/usr/bin/env python3
"""Verify Sentinel's Units Generation dependency graph is acyclic."""
from collections import defaultdict, deque
from pathlib import Path
import re

EDGES = {
    "U1": ["U2"],
    "U2": ["U3", "U4", "U7", "U8"],
    "U3": ["U5", "U8"],
    "U4": ["U5", "U7", "U8"],
    "U5": ["U6"],
    "U6": ["U7"],
    "U7": ["U9"],
    "U8": ["U9"],
    "U9": [],
}


def topological_sort(edges: dict[str, list[str]]) -> list[str]:
    nodes = set(edges)
    indegree = {node: 0 for node in nodes}
    for source, targets in edges.items():
        for target in targets:
            if target not in nodes:
                raise ValueError(f"Unknown dependency node: {target}")
            indegree[target] += 1

    queue = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for target in edges[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(order) != len(nodes):
        cyclic = sorted(node for node, degree in indegree.items() if degree > 0)
        raise ValueError(f"Dependency cycle detected; unresolved nodes: {cyclic}")
    return order


def validate_diagram_text(text: str, label: str) -> None:
    diagram_edges = set()
    for line in text.splitlines():
        match = re.match(r"\s*(U\d+)(?:\[[^]]+\])?\s*-->\s*(U\d+)", line)
        if match:
            diagram_edges.add((match.group(1), match.group(2)))
    expected = {(source, target) for source, targets in EDGES.items() for target in targets}
    if diagram_edges != expected:
        raise ValueError(f"Diagram edge mismatch in {label}: missing={sorted(expected-diagram_edges)}, extra={sorted(diagram_edges-expected)}")


def validate_diagram(path: Path) -> None:
    validate_diagram_text(path.read_text(encoding="utf-8"), str(path))


def validate_backlog_diagram(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    section = re.search(r"^## 4\. Dependencias resumidas entre unidades\s+(.*?)(?=^## 5\.)", text, re.M | re.S)
    if not section:
        raise ValueError("Backlog section 4 dependency graph was not found")
    block = re.search(r"```mermaid\s*(.*?)```", section.group(1), re.S)
    if not block:
        raise ValueError("Mermaid graph was not found in backlog section 4")
    validate_diagram_text(block.group(1), str(path) + " §4")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    order = topological_sort(EDGES)
    validate_diagram(root / "units" / "unit-of-work-dependency.md")
    validate_diagram(root / "diagrams" / "05-units-dependency-graph.mmd")
    validate_backlog_diagram(root / "specs" / "backlog.md")
    edge_count = sum(len(targets) for targets in EDGES.values())
    print(f"OK: {len(EDGES)} units, {edge_count} dependencies, 0 cycles")
    print("OK: all three Mermaid dependency graphs match the verified graph")
    print("Topological order:", " -> ".join(order))
