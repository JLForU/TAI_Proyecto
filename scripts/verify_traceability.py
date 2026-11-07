#!/usr/bin/env python3
"""Verify backlog metadata, map coverage, story dependencies, and unit ownership."""
from __future__ import annotations
import ast
import re
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "specs" / "backlog.md"
UNITS = ROOT / "units" / "unit-of-work.md"
STORY_MAP = ROOT / "units" / "unit-of-work-story-map.md"
CONSOLIDATED = ROOT / "units" / "unidades-y-tareas.md"
UNIT_GRAPH = ROOT / "scripts" / "verify_unit_dag.py"


def parse_stories(text: str):
    blocks = re.split(r"(?=^#### SN-\d{3})", text, flags=re.MULTILINE)
    stories, dependencies = [], {}
    for block in blocks:
        match = re.match(r"^#### (SN-\d{3}) — (.*)", block)
        if not match:
            continue
        sid, title = match.groups()
        owner = re.search(r"^\*\*Unidad:\*\* (U\d+)", block, re.M)
        criterion = re.search(r"^\*\*Criterio de aceptación:\*\* .+", block, re.M)
        evidence = re.search(r"^\*\*Evidencia:\*\* .+", block, re.M)
        dep = re.search(r"^\*\*Depende de:\*\* (.*)$", block, re.M)
        if not all((owner, criterion, evidence, dep)):
            raise ValueError(f"Incomplete metadata for {sid}")
        stories.append((sid, title, owner.group(1)))
        dependencies[sid] = re.findall(r"SN-\d{3}", dep.group(1))
    return stories, dependencies


def topo(edges: dict[str, list[str]]) -> list[str]:
    outgoing = {node: [] for node in edges}
    indegree = {node: 0 for node in edges}
    for node, prereqs in edges.items():
        for pre in prereqs:
            if pre not in edges:
                raise ValueError(f"Unknown dependency: {node} -> {pre}")
            outgoing[pre].append(node)
            indegree[node] += 1
    q = deque(sorted(n for n, d in indegree.items() if d == 0))
    order = []
    while q:
        n = q.popleft(); order.append(n)
        for child in sorted(outgoing[n]):
            indegree[child] -= 1
            if indegree[child] == 0:
                q.append(child)
    if len(order) != len(edges):
        raise ValueError("Story dependency cycle detected")
    return order


def parse_consolidated_tasks(text: str):
    tasks = []
    unit_sections = re.finditer(
        r"^### (U\d+) — .*?\n(.*?)(?=^### U\d+ — |^## )",
        text,
        re.MULTILINE | re.DOTALL,
    )
    for match in unit_sections:
        unit_id, body = match.groups()
        block = re.search(
            r"\*\*Tareas trazadas:\*\*\s*\n(.*?)(?=\n\*\*Puerta de salida:\*)",
            body,
            re.DOTALL,
        )
        if not block:
            continue
        for row in re.finditer(
            r"^\|\s*\d+\s*\|\s*([^|]+)\|\s*(SN-\d{3})\s*\|\s*([^|]*)\|",
            block.group(1),
            re.MULTILINE,
        ):
            title, story_id, prereq_text = row.groups()
            prereqs = re.findall(r"SN-\d{3}", prereq_text)
            tasks.append((story_id, unit_id, title.strip(), prereqs))
    return tasks


def unit_edges():
    tree = ast.parse(UNIT_GRAPH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EDGES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("EDGES not found in unit graph verifier")


def main() -> int:
    stories, deps = parse_stories(BACKLOG.read_text(encoding="utf-8"))
    ids = [s[0] for s in stories]
    if len(ids) != 47 or len(set(ids)) != len(ids):
        raise ValueError(f"Expected 47 unique stories, found {len(ids)}")
    units_text = UNITS.read_text(encoding="utf-8")
    declared = set(re.findall(r"^### (U\d+) —", units_text, re.M))
    owners = {s[2] for s in stories}
    if owners != declared:
        raise ValueError(f"Unit ownership mismatch: backlog={sorted(owners)}, definitions={sorted(declared)}")

    map_text = STORY_MAP.read_text(encoding="utf-8")
    coverage = map_text.split("## Cobertura por unidad", 1)[1].split("## Matriz de verificación", 1)[0]
    coverage_rows = {}
    for line in coverage.splitlines():
        if not line.startswith("|") or "SN-" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        unit_match = re.search(r"(U\d+)", cells[0])
        story_ids = re.findall(r"SN-\d{3}", cells[1]) if len(cells) > 1 else []
        if unit_match:
            for sid in story_ids:
                if sid in coverage_rows:
                    raise ValueError(f"Duplicate story in coverage: {sid}")
                coverage_rows[sid] = unit_match.group(1)

    matrix_rows = {}
    matrix_section = map_text.split("## Matriz de verificación", 1)[1]
    for line in matrix_section.splitlines():
        if not line.startswith("| ["):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        sid_match = re.search(r"SN-\d{3}", cells[0]) if cells else None
        if not sid_match or len(cells) < 5:
            continue
        sid = sid_match.group(0)
        if sid in matrix_rows:
            raise ValueError(f"Duplicate story in verification matrix: {sid}")
        matrix_rows[sid] = (cells[1], re.findall(r"SN-\d{3}", cells[4]))

    if set(coverage_rows) != set(ids) or set(matrix_rows) != set(ids):
        raise ValueError(f"Story map mismatch: coverage missing={sorted(set(ids)-set(coverage_rows))}, matrix missing={sorted(set(ids)-set(matrix_rows))}")
    owner = {sid: uid for sid, _, uid in stories}
    for sid in ids:
        if coverage_rows[sid] != owner[sid]:
            raise ValueError(f"Coverage owner mismatch for {sid}: map={coverage_rows[sid]}, backlog={owner[sid]}")
        matrix_owner, matrix_prereqs = matrix_rows[sid]
        if matrix_owner != owner[sid]:
            raise ValueError(f"Matrix owner mismatch for {sid}: map={matrix_owner}, backlog={owner[sid]}")
        if set(matrix_prereqs) != set(deps[sid]):
            raise ValueError(f"Matrix prerequisites differ for {sid}: map={sorted(matrix_prereqs)}, backlog={sorted(deps[sid])}")

    consolidated_tasks = parse_consolidated_tasks(CONSOLIDATED.read_text(encoding="utf-8"))
    task_ids = [row[0] for row in consolidated_tasks]
    if len(task_ids) != 47 or len(set(task_ids)) != len(task_ids):
        missing = sorted(set(ids) - set(task_ids))
        duplicates = sorted(k for k, c in Counter(task_ids).items() if c > 1)
        raise ValueError(f"Consolidated task map must contain each story once; missing={missing}, duplicates={duplicates}")
    for sid, unit_id, title, prereqs in consolidated_tasks:
        if owner[sid] != unit_id:
            raise ValueError(f"Consolidated task {sid} is in {unit_id}, backlog owner is {owner[sid]}")
        if set(prereqs) != set(deps[sid]):
            raise ValueError(f"Direct prerequisites differ for {sid}: task table={sorted(prereqs)}, backlog={sorted(deps[sid])}")

    order = topo(deps)
    dist = {n: 1 for n in order}; pred = {n: None for n in order}
    for n in order:
        for child, prereqs in deps.items():
            if n in prereqs and dist[child] < dist[n] + 1:
                dist[child] = dist[n] + 1; pred[child] = n
    end = max(order, key=lambda n: dist[n]); path = [end]
    while pred[path[-1]] is not None: path.append(pred[path[-1]])
    path.reverse()

    # Every cross-unit story prerequisite must be represented by a path in the unit DAG.
    uedges = unit_edges()
    reach = {u: set() for u in uedges}
    for source in uedges:
        stack = list(uedges[source])
        while stack:
            target = stack.pop()
            if target not in reach[source]:
                reach[source].add(target)
                stack.extend(uedges[target])
    for sid, pres in deps.items():
        for pre in pres:
            a, b = owner[pre], owner[sid]
            if a != b and b not in reach[a]:
                raise ValueError(f"Unit graph does not express story dependency path {a} -> {b} ({pre} -> {sid})")

    print(f"OK: {len(ids)} unique stories; {len(declared)} units; one owner per story")
    print("OK: coverage and story-map matrix contain every story once with matching owner and dependencies")
    print("OK: consolidated task table contains every story once with matching owner and direct prerequisites")
    print("OK: all criteria/evidence/dependencies are present in backlog")
    print("OK: story graph and unit graph are acyclic; cross-unit dependencies are represented")
    print(f"Longest story chain ({len(path)}):", " -> ".join(path))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
