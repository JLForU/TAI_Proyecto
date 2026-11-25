#!/usr/bin/env python3
import re

answers = {
    1: "C — Spanish body with English identifiers (consistente con PRD/PVB en español y requirements.md en inglés)",
    2: "A — Feature-based by module (M1..M9) con matriz de trazabilidad FR→story",
    3: "A — Three personas: Network Operator, Platform Administrator, Security Reviewer",
    4: "A — Given/When/Then + Verification: line with exact command or measurable check",
    5: "A — Functional stories + separate Enabler stories section for verifiable NFRs",
    6: "A — MoSCoW aligned with PRD §8",
    7: "A — Target commands defined now (helm, kubectl, curl, pytest); runnable once implemented",
}

path = "aidlc-docs/inception/plans/story-generation-plan.md"
with open(path) as f:
    content = f.read()

count = 0
def replacer(m):
    global count
    count += 1
    return f"[Answer]: {answers.get(count, '')}"

new_content = re.sub(r"^\[Answer\]:[ ]*$", replacer, content, flags=re.MULTILINE)

with open(path, "w") as f:
    f.write(new_content)

print(f"Rellenadas {count} respuestas")
