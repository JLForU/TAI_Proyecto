# NFR Requirements Plan — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 1: Planning)
**Fecha**: 2026-11-16
**Estado**: GENERATED — respuestas todas A (2026-11-16); artefactos generados; pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/`
**Entradas**: `construction/u4-discovery/functional-design/*` (aprobado 2026-11-16T17:44:07Z), `requirements.md` §3 NFR + §4 constraints + §5, U1 `tech-stack-decisions.md` (TS-01..11), U2 (TS-U2-01..10), U3 (TS-U3-01..11), `implementation-scope.md`.

---

## 1. Contexto del assessment (Step 1 — analizado)

U4 es el **colector con efectos en la red real**: sondea dentro de una allowlist, lanza subprocess (`nmap`, `ping`, `ip neigh`), y es el primer módulo que depende de binarios externos y de un deadline de ciclo. Sus NFR tocan rendimiento de ciclo (NFR-PERF-01 no vinculante), seguridad del escaneo (superficie de subprocess, flags prohibidos, non-root), fiabilidad ante binarios/Core ausentes (degradación a fixtures, exit codes), y mantenibilidad (PBT de Nmap XML ya exigido por NFR-TECH-03, gate de cobertura propio, tests sin red real).

**Ya decidido (NO se pregunta)**:
- **PBT obligatorio para Nmap XML** en U4 (NFR-TECH-03, `requirements.md` §5 — designado a esta unidad).
- Python 3.11 + stdlib + `httpx` + `hypothesis` (dev) — sin dependencias de runtime nuevas en U4 (FD §3.4: subprocess stdlib).
- Contenedor non-root (NFR-SEC-02); ICMP sin raw sockets (FD D-U4-05).
- Intervalo default 15 min (FR-DISC-03); env `SENTINEL_DISCOVERY_*` con loader propio y fail-fast (FD §3.1); Helm values llegan en U9 (NFR-OPS-01).
- Reintentos con `foundation.retry` (attempts=5, D-U4-03); Bearer `SENTINEL_INGEST_TOKEN` (U2).
- Logs JSON estructurado con `component`/`event` (BR-12 U1); exit codes 0/1 (BR-U4-32).
- Fallback a fixtures si falta nmap (BR-U4-18); flags prohibidos por whitelist (BR-U4-10/11).
- FQ1=C: sin métrica de fallos standalone (D-U4-01); sin auth nueva; sin UI (Usability no aplica).
- CI actual: global `--cov-fail-under=70` + gate `gui/` ≥70; gates por unidad precedente: `core/` ≥70 (TS-U2-10), `gui/` ≥70 (TS-U3-xx).

**Categorías evaluadas**:

| Categoría | Aplica a U4 | Tratamiento |
|---|---|---|
| Scalability | Sí | Q2 (cap de targets por ciclo y lote único ≤1000) |
| Performance | Sí | Q1 (duración de ciclo vs NFR-PERF-01 no vinculante) |
| Availability | Parcial | Degradación ya cerrada en FD (fallback fixtures, exit 1, retry); sin pregunta |
| Security | Sí | Q4 (aislamiento de subprocess), Q8 (rígidez de config); allowlist/whitelist/token ya en FD (BR-U4-06..11, NFR-SEC-01) |
| Tech Stack | Parcial | Q5 (scapy vs stdlib), Q9 (pin de versión de nmap); resto fijado (TS-01..11) |
| Reliability | Sí | Q3 (reparto del deadline entre fases); degradación y códigos ya en FD |
| Maintainability | Sí | Q6 (gate `discovery/` ≥70), Q7 (tests sin red real) |
| Usability | **No aplica** | U4 sin UI (única con UI es U3) |

---

## 2. Checklist del plan

- [x] Analizar Functional Design y NFR globales
- [x] Generar preguntas NFR (Q1–Q9)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-16: "Acepto todo" ⇒ Q1–Q9 = A)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `nfr-requirements/nfr-requirements.md`
- [x] Generar `nfr-requirements/tech-stack-decisions.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Duración del ciclo de descubrimiento (Performance / NFR-PERF-01)

Contexto: NFR-PERF-01 ("Discovery scan <60s for /24") es **no vinculante** (validado en lab); U2 y U3 usaron baseline informativo sin gate. El ciclo de U4 tiene 4 fases y un deadline configurable (default 30 s).

A) Test **informativo** de duración de ciclo con `FixtureScanner` (imprime duración total y por fase en la suite, sin bloquear CI) — misma bar que U2/U3 *(recomendado)*

B) Gate de CI: ciclo con fixtures <60 s (flaky en runners compartidos)

C) Sin medición de duración en U4

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Cap de targets por ciclo (Scalability)

Contexto: la expansión de un CIDR sin límite puede generar miles de hosts; `DiscoveryRequest` de U2 acepta ≤1000 hosts y `Batch` ≤1000 items; U4 emite **1 observación por host** ⇒ con ≤1000 targets el lote siempre cabe en un solo POST (BR-U4-21).

A) **Cap de 1000 targets por ciclo** (alineado a `MAX_BATCH_ITEMS` y al límite de `DiscoveryRequest`): la expansión de cidr se valida/trunca y una config que supere el cap ⇒ `ConfigError` fail-fast — un solo POST por ciclo siempre *(recomendado)*

B) Cap de 1024 (holgura de 24) aceptando que el lote se parte en 2 POSTs cuando excede 1000

C) Sin cap: cualquier rango (p. ej. /8) se sondea entero dentro del deadline

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Reparto del deadline entre fases (Reliability)

Contexto: el ciclo tiene 4 fases (arp → icmp → tcp → nmap) con un deadline total (default 30 s); si una fase es lenta (p. ej. `ping` con hosts caídos), puede consumir el deadline entero y las fases siguientes nunca corren (BR-U4-14 exige chequeo entre fases).

A) **Reparto proporcional fijo**: arp 20% / icmp 30% / tcp 30% / nmap 20% del `timeout_seconds`; cada fase se corta en su cupo y el ciclo continúa con la siguiente (todas las fases corren siempre dentro del deadline) *(recomendado)*

B) Greedy: cada fase usa el deadline restante completo (la primera fase puede consumirlo todo)

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Aislamiento del escaneo (Security)

Contexto: U4 ejecuta binarios del sistema (`nmap`, `ping`, `ip neigh`) en un contenedor non-root (NFR-SEC-02); los flags de nmap ya tienen whitelist (BR-U4-10/11) y NFR-SEC-01 exige SECURITY blocking.

A) **subprocess sin shell** (`shell=False`, argv como lista), whitelist de flags antes de ejecutar, PATH fijo de la imagen, fixtures con path canónico bajo `tests/fixtures/` (sin traversal), sin NSE/scripts jamás *(recomendado)*

B) Sandbox adicional para nmap (nsjail/bubblewrap) — aislamiento más fuerte, dependencia y complejidad extra para lab

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — scapy en U4 (Tech Stack)

Contexto: NFR-TECH-02 menciona `scapy` en el stack global (pensado para captura/ARP de U5); el FD de U4 resolvió ARP/ICMP/TCP sin raw sockets (`ip neigh`, `ping`, stdlib) porque el contenedor es non-root (NFR-SEC-02).

A) **Sin scapy en U4**: ARP vía tabla del sistema, ICMP vía binario `ping`, TCP vía stdlib — cero dependencias nuevas y sin capacidades especiales en el pod *(recomendado)*

B) scapy en U4 con `cap_net_raw` concedida al worker (más control de paquetes; exige capability en Deployment/CronJob de U9)

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Gate de cobertura de `discovery/` (Maintainability)

Contexto: CI global `--cov-fail-under=70`; precedentes por unidad: `core/` ≥70 (TS-U2-10), `gui/` ≥70 (U3). U4 añade un paquete nuevo con lógica de red y parsing.

A) Gate adicional **`discovery/` ≥70%** en CI (misma bar que las unidades anteriores, verificable con `coverage report --include='*/discovery/*'`) *(recomendado)*

B) Sin gate propio: solo el global 70%

C) Gate más estricto ≥90% para `discovery/`

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Tests sin red real (Testing / Reliability)

Contexto: el CI no debe depender de red, binarios de escaneo ni de la LAN; los AC de U4 se verifican con `pytest` (`test_scope_validation`, `test_nmap_args`, `test_config_validation`, `test_gt02/gt03`, `test_discovery_failure`).

A) **Ningún test de U4 toca la red real**: `nmap`/`ping`/`ip neigh` mockados o `FixtureScanner`, validación de alcance pura; el sondeo real queda para el Build & Test en el lab (kind/k3s) *(recomendado)*

B) Tests de integración con loopback real (127.0.0.1) para TCP connect

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Riguez de la configuración del worker (Security / Maintainability)

Contexto: loader propio con patrón `foundation.config` (`extra="forbid"`, fail-fast BR-07); el intervalo y el timeout tienen rangos razonables (timeout 1..3600 alineado a U2).

A) **Estricta**: claves `SENTINEL_DISCOVERY_*` desconocidas ⇒ `ConfigError` (un typo no debe pasar silencioso), `interval_minutes ≥ 1`, `timeout_seconds ∈ [1, 3600]`, puertos sin duplicados *(recomendado)*

B) Tolerante: claves desconocidas se ignoran con warning (solo fallar por valores inválidos)

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Versión mínima de nmap (Tech Stack)

Contexto: el escáner usa `-sT -sV --version-light -oX -` (FR-DISC-02); si falta el binario hay fallback a fixtures (BR-U4-18); la imagen de lab se define en U9.

A) **Sin pin de versión**: cualquier nmap que soporte esos flags; la imagen instala el paquete del distro; ausente ⇒ fallback fixtures con warning *(recomendado)*

B) Exigir nmap ≥7.90 al arrancar el worker (`ConfigError` si inferior o ausente con `SCANNER=nmap`)

C) Other (describe después de `[Answer]:`)

[Answer]: A
