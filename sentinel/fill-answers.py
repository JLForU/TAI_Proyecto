#!/usr/bin/env python3
import re

answers = {
    1:  "A",
    2:  "A — 15 min por defecto, configurable vía Helm values",
    3:  "A — AF_PACKET/TPACKET_V3 sobre bridge/SPAN. Requiere hostNetwork en el Pod del sensor",
    4:  "B — configurable 1s/5s/10s/30s/60s, default 5s",
    5:  "A — baseline engine con k configurable y umbral absoluto como fallback; no alertar durante los primeros 25s",
    6:  "C — ARP request + reply (opcodes 1 y 2)",
    7:  "A — SQLite en PVC",
    8:  "B — HTTP/JSON only, /metrics para Prometheus",
    9:  "C — single sensor MVP con sensor_id reservado",
    10: "C — SNMP como módulo opcional vía Helm, no obligatorio en MVP",
    11: "B — Sentinel chart separado, kube-prometheus-stack aparte",
    12: "B — webhook only; documentar webhook.site para demos",
    13: "A — default-deny NetworkPolicy; documentar requisito de CNI compatible (Calico/Cilium/k3s)",
    14: "A — CAP_NET_RAW + CAP_NET_ADMIN + CAP_SYS_ADMIN; evaluar si CAP_SYS_ADMIN se puede dropear",
    15: "A — JSON Lines para eventos, CSV para bulk export",
    16: "B — 5 casos core; los 11 son stretch",
    17: "A — enforce all SECURITY rules (proyecto enfocado en seguridad)",
    18: "B — skip (prototipo académico, no producción)",
    19: "B — partial PBT (parsing XML Nmap, normalización, baseline)",
    20: "A — vanilla Kubernetes 1.28+, testeado en kind/k3s",
    21: "B — Alpine base (minimal attack surface)",
    22: "A — Python para todo (FastAPI + scapy)",
    23: "A — full CI; B si el tiempo aprieta",
    24: "A — markdown en repo",
}

path = "aidlc-docs/inception/requirements/requirement-verification-questions.md"
with open(path) as f:
    content = f.read()

count = 0
def replacer(m):
    global count
    count += 1
    ans = answers.get(count, "")
    return f"[Answer]: {ans}"

new_content = re.sub(r"^\[Answer\]:[ ]*$", replacer, content, flags=re.MULTILINE)

with open(path, "w") as f:
    f.write(new_content)

print(f"Rellenadas {count} respuestas")
