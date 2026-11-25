# NFR Requirements Plan — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — NFR Requirements (Parte 1: Planning)
**Fecha**: 2026-11-18
**Estado**: GENERATED — respuestas todas A (2026-11-18); artefactos generados; pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/`
**Entradas**: `construction/u5-traffic/functional-design/*` (aprobado 2026-11-18T16:53:34Z), `requirements.md` §3 NFR + §4 constraints + §5, U1 `tech-stack-decisions.md` (TS-01..11), U2 (TS-U2-01..11), U3 (TS-U3-01..11), U4 (TS-U4-01..12), `implementation-scope.md`.

---

## 1. Contexto del assessment (Step 1 — analizado)

U5 es el **colector de sensor**: no toca la red real en el MVP (fuente abstracta + simulador/fixtures), no persiste, no expone métricas; habla con el Core solo por HTTP con reintentos. Sus NFR tocan rendimiento de ingesta (NFR-PERF-02 ≥10k flows/s, no vinculante), cardinalidad de lotes por ventana (burst ARP vs `MAX_BATCH_ITEMS`), fiabilidad ante fallos de fuente/reloj (loop que no debe morir), seguridad (sin capabilities en el MVP; token mínimo; sin payload), y mantenibilidad (gate `traffic/`, tests sin red/SCAPY, PBT opcional de agregación más allá de los tres designados en NFR-TECH-03).

**Ya decidido (NO se pregunta)**:
- **Sin dependencias pip nuevas**: sin `scapy` (captura real documentada, FD Q3=A/D-U5-07); stdlib + `httpx` + `foundation.*`; `hypothesis` solo dev.
- **NFR-AVAIL-01** (single sensor, gap aceptado): cerrado en FD D-U5-05 (descarte de ventana tras reintentos, sin buffer).
- **Heartbeat sin endpoint propio** (FD BR-U5-28); GT-05 = detener loop.
- **Config estricta** `SENTINEL_TRAFFIC_*` con ventana ∈ {1,5,10,30,60} y `extra="forbid"` (FD BR-U5-01/02).
- **Reintentos** `foundation.retry` ×5 + Bearer `SENTINEL_INGEST_TOKEN` (FD BR-U5-24/25, hereda TS-U2-09/TS-U4-05).
- **Non-root** en la imagen (NFR-SEC-02); capabilities del sensor (FR-TRAF-02) son diseño documentado + valores de U9 (FD §5, OQ-01 en NFR Design/Infra).
- **Logs JSON estructurado** con `component`/`event` canónicos (BR-12 U1); exit codes 0/1 (BR-U5-29).
- **PBT designado por NFR-TECH-03**: Nmap XML (U4 ✓), flow normalization (U2 ✓), baseline (U6 pendiente) — **U5 no está en la lista designada** (pero ver Q8).
- **CI actual**: global `--cov-fail-under=70` + gates `core/` ≥70 (TS-U2-10), `gui/` ≥70 (U3), `discovery/` ≥70 (TS-U4-08).
- **Sin UI** (Usability no aplica — única unidad con UI es U3).
- **NFR-OPS-01** (Helm values): U5 solo publica env listas para el mapeo de U9 (FD §5).

**Categorías evaluadas**:

| Categoría | Aplica a U5 | Tratamiento |
|---|---|---|
| Scalability | Sí | Q2 (chunking de lote ante ráfaga ARP vs `MAX_BATCH_ITEMS`) |
| Performance | Sí | Q1 (baseline informativo NFR-PERF-02) |
| Availability | Parcial | ya cerrado en FD (D-U5-05, heartbeat, GT-05); Q3 (fallo de fuente a mitad de ventana) |
| Security | Sí | Q4 (capabilities/privilegios), Q5 (config estricta); token/sin payload ya en FD |
| Tech Stack | Parcial | fijado: sin scapy, Python 3.11, httpx, hypothesis dev (FD Q3) |
| Reliability | Sí | Q3 (fuente), Q9 (semántica de reloj) |
| Maintainability | Sí | Q6 (gate `traffic/` ≥70), Q7 (tests sin red/sockets), Q8 (PBT agregación) |
| Usability | **No aplica** | U5 sin UI |

---

## 2. Checklist del plan

- [x] Analizar Functional Design y NFR globales
- [x] Generar preguntas NFR (Q1–Q9)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-18: "Acepto todo" ⇒ Q1–Q9 = A)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; interacciones revisadas (Q2×FD §3.5 chunking; Q3×Q9 loop/heartbeat; Q4×FD Q3 sin scapy) ⇒ **sin FQ necesarias**
- [x] Generar `nfr-requirements/nfr-requirements.md`
- [x] Generar `nfr-requirements/tech-stack-decisions.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Baseline de rendimiento del sensor (Performance / NFR-PERF-02)

Contexto: NFR-PERF-02 ("Sensor ≥10k flows/s on 2 cores") es **no vinculante** (validado en lab); U2/U3/U4 usaron baseline informativo sin gate en CI. El `SimulatedSource` permite medir el pipeline (fuente → agregación → proyección) sin red.

A) Test **informativo** de throughput con `SimulatedSource` a tasa alta (imprime flows/s y duración de la suite, **sin gate** en CI); la envolvente real (≥10k flows/s en 2 cores) se valida en el lab durante Build & Test — misma bar que U2/U3/U4 *(recomendado)*

B) Gate de CI: ≥10k flows/s en el runner (flaky en runners compartidos)

C) Sin medición de rendimiento en U5

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Cardinalidad de lote por ventana (Scalability)

Contexto: un `POST` por ventana (FD §3.5) con lote mixto; `Batch` de U1 admite ≤1000 items; una **ráfaga ARP** (o alta concurrencia) puede generar cientos de `ArpObservation` en una ventana de 60 s y superar el límite ⇒ 422 de U2.

A) **Chunking del export**: partir los items de la ventana en POSTs secuenciales de ≤1000 (`chunks` de `Batch`); si un chunk falla tras reintentos se descartan **solo los chunks no entregados** de esa ventana (mismo precedente D-U5-05) — nunca un `Batch` >1000 *(recomendado)*

B) Cap de ARP por ventana (p. ej. ≤900) descartando el excedente con log (pierde observaciones en ráfaga)

C) Un solo POST siempre; confiar en que la ráfaga no excede 1000 (riesgo de 422 en la demo)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Fallo de la fuente a mitad de ventana (Reliability)

Contexto: `PacketSource` puede fallar (fixture corrupta, bug del simulador); el loop de `--loop` **no debe morir** (si muere, cae el heartbeat ⇒ GT-05 en falso).

A) **Ventana abortada, loop vivo**: log `event="sensor_source_error"` + causa, se descarta el acumulador parcial, el loop continúa con la siguiente ventana (`--once` ⇒ exit 1); sin reintento de la fuente en la misma ventana *(recomendado)*

B) El proceso termina con exit 1 en ambos modos (el orquestador/K8s reinicia el Pod)

C) Reintentar la fuente dentro de la misma ventana hasta que recupere

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Privilegios y capabilities del sensor en el MVP (Security / NFR-SEC-01/02)

Contexto: FR-TRAF-02 exige `hostNetwork` + `CAP_NET_RAW/NET_ADMIN/SYS_ADMIN` para la captura real; el MVP **solo** corre `SimulatedSource`/`FixtureSource` (sin sockets crudos, sin scapy — FD Q3); NFR-SEC-02 pide Alpine non-root "except sensor capabilities"; OQ-01 (¿se puede dropear `CAP_SYS_ADMIN`?) se resuelve en NFR Design/Infra.

A) **U5 code sin privilegios**: el paquete no requiere capabilities ni `hostNetwork` (simulador/fixtures); la imagen sigue **non-root** (NFR-SEC-02); el diseño documentado de AF_PACKET y los `securityContext`/`hostNetwork` del Pod quedan para U9 con las notas de capabilities (incluida la evaluación OQ-01) *(recomendado)*

B) Preparar ya el `securityContext` con las 3 capabilities en manifiestos de U5 (no hay manifiestos hasta U9)

C) Implementar `AfPacketSource` en U5 exigiendo capabilities (contradice FD Q3=A)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Riguez de la configuración del sensor (Security / Maintainability)

Contexto: loader propio con patrón `foundation.config` (`extra="forbid"`, fail-fast BR-U5-01/02); un typo en `SENTINEL_TRAFFIC_*` no debe pasar silencioso.

A) **Estricta**: claves `SENTINEL_TRAFFIC_*` desconocidas ⇒ `ConfigError`; `window ∈ {1,5,10,30,60}`; `sim_rate > 0`; `interface`/`sensor_id` no vacíos; `fallback=false` ⇒ `ConfigError` (D-U5-07) *(recomendado)*

B) Tolerante: claves desconocidas se ignoran con warning (solo fallar por valores inválidos)

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Gate de cobertura de `traffic/` (Maintainability)

Contexto: CI global `--cov-fail-under=70`; precedentes por unidad: `core/` ≥70 (TS-U2-10), `gui/` ≥70 (U3), `discovery/` ≥70 (TS-U4-08). U5 añade el paquete del sensor.

A) Gate adicional **`traffic/` ≥70%** en CI (misma bar que las unidades anteriores, `coverage report --include='*/traffic/*' --fail-under=70`) *(recomendado)*

B) Sin gate propio: solo el global 70%

C) Gate más estricto ≥90% para `traffic/`

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Tests sin red real ni sockets crudos (Testing / Security)

Contexto: el CI no debe depender de LAN, SPAN ni capabilities; la frontera de U5 (FD BR-U5-32/33) ya prohíbe scapy y `sentinel.core`.

A) **Ningún test de U5 toca la red real ni abre sockets**: todo con `SimulatedSource`/`FixtureSource` + `TestClient` de U2; sin `socket` crudo, sin `scapy`, sin binarios de red; la captura real queda documentada (Build & Test solo levanta el stack con el simulador) *(recomendado)*

B) Tests de integración con loopback (127.0.0.1) para el POST real

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — PBT de agregación de ventanas (Maintainability / NFR-TECH-03)

Contexto: NFR-TECH-03 designa PBT a Nmap XML (U4 ✓), flow normalization (U2 ✓) y baseline (U6) — **U5 no está designado**; `hypothesis` ya está en dev; la agregación es la lógica central de U5 (partitionado del tiempo, conservación de bytes, determinismo).

A) **PBT adicional opcional** en `tests/property/test_window_aggregation.py`: (a) las ventanas particionan la línea temporal sin solapes ni huecos, (b) Σ `packet_length_bytes` de los grupos == Σ bytes de los eventos de la ventana, (c) mismo `(seed, rate)` ⇒ mismas observaciones — refuerza MNT sin contradecir NFR-TECH-03 *(recomendado)*

B) Sin PBT en U5 (solo los tres designados en NFR-TECH-03; tests unitarios de casos bastan)

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Semántica de reloj para las ventanas (Reliability)

Contexto: las ventanas son **epoch-aligned UTC** (`floor(now/W)*W`, FD BR-U5-12); el reloj de pared puede saltar por NTP; los tests necesitan control total del tiempo (FD: reloj inyectable).

A) **Pared UTC para ventanas** (`datetime.now(UTC)` inyectable vía protocolo de reloj; en tests, reloj falso que avanza a demanda — sin `sleep`); `monotonic` solo para el backoff de reintentos — alineación estable con sistemas externos (Core, Prometheus) *(recomendado)*

B) `monotonic` para las ventanas (inmune a NTP pero se desfasará del reloj del Core/Prometheus; imposible de alinear con timestamps externos)

C) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Follow-up (Step 5 — ambigüedad detectada)

> Análisis de interacciones Q2×FD §3.5 (chunking coherente con 1 POST/ventana: chunk es desglose del mismo cierre), Q3×Q9 (loop vivo + reloj inyectable), Q4×FD Q3 (sin scapy ⇒ sin caps): todas resueltas por A. **Sin follow-ups.**
