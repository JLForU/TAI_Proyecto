# NFR Design Plan — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — NFR Design (Parte 1: Planning)
**Fecha**: 2026-11-16
**Estado**: GENERATED — respuestas todas A (2026-11-16); artefactos generados; pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/`
**Entradas**: `construction/u4-discovery/nfr-requirements/*` (aprobado 2026-11-16T18:33:50Z: NFR-U4-PERF/SCAL/AVAIL/REL/SEC/MNT/TECH, TS-U4-01..12), Functional Design de U4 (aprobado), `nfr-design` de U2/U3 (patrones de referencia), `foundation` (retry/logging/metrics_contract).

---

## 1. Contexto del assessment (Step 1 — analizado)

Cómo incorporar los NFR aprobados de U4 en **patrones de diseño y componentes lógicos** concretos: qué pasa cuando un ciclo falla en el loop, si el CronJob y el trigger manual pueden correr a la vez, cómo ejecutar las sondas para cumplir el deadline, cómo tratar los datos no confiables que vienen de la red, y cómo se inyectan/testean el escáner, la ingesta y los contadores (seams de prueba + wiring en CI.

Ya decidido en etapas previas (NO se pregunta): degradación por capas con fallback fixtures (AVAIL-01), worker sin estado + SIGTERM entre ciclos (AVAIL-02), reparto de deadline 20/30/30/20 (REL-01/TECH-04), allowlist + whitelist de flags + subprocess `shell=False` (SEC-01/02), non-root sin scapy/caps (SEC-03), token mínimo (SEC-04), gate `discovery/` ≥70% (MNT-01), tests sin red real (MNT-02), PBT Nmap XML (MNT-03), logging canónico sin métricas propias (MNT-04, FQ1=C), cero deps pip (TECH-01), nmap sin pin (TECH-02), config estricta (TECH-03), cap 1000 targets + lote único (SCAL-01), baseline informativo de duración (PERF-01), reparto de deadline (Q3 NFR Req), inyección de runner lazy (FD Q15).

**Categorías evaluadas** (todas las obligatorias):

| Categoría | Aplica a U4 | Tratamiento |
|---|---|---|
| Resilience Patterns | Sí | Q1 (continuidad del `--loop` tras un ciclo fallido), Q2 (concurrencia CronJob ↔ trigger manual) |
| Scalability Patterns | Cerrado | **Sin pregunta**: SCAL-01 (cap 1000 targets, lote único) ya fijado en NFR Req; crecimiento >1000 se revisa en U11 (misma bar que NFR-U2-SCAL-01/U3) |
| Performance Patterns | Sí | Q3 (paralelismo de sondas dentro de cada fase), Q4 (timeouts por sonda) |
| Security Patterns | Sí | Q5 (datos de red no confiables → validación/log); transporte heredado de U2 (HTTP plano + NetworkPolicy de U9, NFR-U2-SEC-01) sin mitigación extra en U4 |
| Logical Components | Sí | Q6 (seams de inyección: scanner/ingest/settings por constructor), Q7 (wiring del `CycleCounter`), Q8 (gate de cobertura como step de CI) |

---

## 2. Checklist del plan

- [x] Analizar NFR requirements aprobados
- [x] Generar preguntas de diseño NFR (Q1–Q8)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-16: "Acepto todo" ⇒ Q1–Q8 = A)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `nfr-design/nfr-design-patterns.md`
- [x] Generar `nfr-design/logical-components.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Continuidad del `--loop` tras un ciclo fallido (Resilience Patterns)

Contexto: NFR-U4-AVAIL-01 fija degradación por capas y exit 1 en `--once`; en `--loop` (demo sin chart) un ciclo puede fallar (Core caído tras reintentos, scope violation, escáner caído) y el worker sigue vivo hasta SIGTERM (AVAIL-02).

A) **El loop continúa**: un ciclo fallido se registra (log + causa) y el worker duerme hasta el siguiente intervalo para reintentar el ciclo — los fallos son **por ciclo**, sin estado acumulado, sin circuit breaker ni contador de fallos consecutivos *(recomendado)*

B) **Circuit breaker ligero**: tras N (p. ej. 3) fallos consecutivos, el worker se retira (exit 1) para que el CronJob/K8s gestione el reinento

C) Parar el loop en el primer fallo (fail-fast total, como `--once`)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Concurrencia: trigger manual (API) vs CronJob `--once` (Resilience Patterns)

Contexto: el lock único de U2 (409) protege **solo** los runs creados por `POST /discovery` dentro del proceso Core; el CronJob de U9 correrá `--once` como proceso aparte — en lab, un operador puede disparar desde la GUI mientras corre el Job programado (dos escaneos simultáneos; el dedup de U2 hace idempotente el doble envío).

A) **Aceptar la concurrencia en lab**: sin lock entre procesos; los dos ciclos son independientes y el dedup UUIDv5 de U2 absorbe observaciones duplicadas; documentado como limitación (el lock cross-proceso llegaría con almacenamiento compartido, fuera del MVP) *(recomendado)*

B) Lock entre procesos con fichero de lock en volumen compartido (complejidad + frontera "sin DB" del worker)

C) El worker `--once` consulta `GET /discovery` antes de correr y se salta el ciclo si hay uno `running` (best-effort, sin atomicidad)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Paralelismo de sondas dentro de cada fase (Performance Patterns)

Contexto: NFR-U4-SCAL-01 permite hasta 1000 targets; una fase seriales con timeout por sonda de 1 s podría consumir su cupo (20–30% de 30 s) mucho antes de cubrir un /24; REL-01 exige que todas las fases corran dentro del deadline.

A) **`ThreadPoolExecutor` acotado por fase** (p. ej. 32 hilos máximo, `atexit`/shutdown ordenado) para ICMP/TCP sobre los targets del cupo; ARP y nmap siguen siendo una sola llamada por fase — paralelismo limitado, determinista en resultados (orden de hallazgos normalizado al fusionar) *(recomendado)*

B) Sondas 100% seriales (más simple y determinista al milisegundo; riesgo de no cubrir /24 dentro del cupo)

C) Sin límite de hilos (un hilo por target — abre cientos de hilos con el cap de 1000)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Timeouts por sonda (Performance Patterns)

Contexto: cada sonda necesita su propio timeout para no agotar el cupo de fase (ping a host caído, connect a puerto filtrado).

A) **Timeouts fijos codificados**: `ping -W 1` (1 s), `socket.connect` con 1 s, ventana de `ip neigh` instantánea (tabla local) — valores constantes de módulo, testeables, sin claves nuevas de env *(recomendado)*

B) Configurables por env (`SENTINEL_DISCOVERY_PING_TIMEOUT`, `..._CONNECT_TIMEOUT`) — más flexibles, añade 2 claves al loader estricto

C) Derivados del cupo de fase (timeout por sonda = cupo/nº targets — variable, difícil de testear)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Datos de red no confiables hacia logs y persistencia (Security Patterns)

Contexto: hostname, servicio y versión vienen de la red (XML de nmap, tabla ARP) y llegan a la BD (U2) y a los logs; SEC-01/SEC-04 cubren allowlist y secretos, pero no la confianza en el *contenido* de los hallazgos (log injection, strings enormes, control chars).

A) **Validación en el contrato + JSON estructurado**: todo hallazgo se convierte a `DiscoveryObservation` de U1 (Pydantic: longitudes ≤255, formatos IP/MAC, puertos 1..65535) **antes** del POST; los logs son JSON con campos separados (`foundation.logging`) ⇒ el contenido de red nunca se interpreta como formato de log; sin sanitización extra *(recomendado)*

B) Sanitización explícita además de Pydantic (strip de control chars en hostname/service antes de modelar)

C) Escapado/agresivo: truncado y escaping de todo string no alfanumérico

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Seams de inyección para tests (Logical Components)

Contexto: MNT-02 exige tests sin red real; el worker depende de escáner (binarios), cliente HTTP y settings; FD §3.8 ya inyecta el runner en `create_app`.

A) **Inyección por constructor en todo el ensamblaje**: `run_cycle(settings, scanner, ingest_client, ...)`, `CycleRunnerImpl(scanner=..., ingest_client=..., settings=...)` con **defaults reales** para producción; los tests construyen con `FixtureScanner` + `httpx.MockTransport` + settings de test — sin monkeypatch de módulos *(recomendado)*

B) Defaults globales + monkeypatch de `scanner.py`/`client.py` en tests (menos código de producción, tests más frágiles)

C) Factory con registro/lookup (DI container ligero — peso innecesario para lab)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Wiring del `CycleCounter` (Logical Components)

Contexto: FD §3.6/Q8=A pone los contadores `cycles_total`/`cycles_failed_total` en el Core, incrementados por `DiscoveryTrigger`; el `collect()` de U2 ya recibe `api_requests` y `heartbeats` por parámetro (patrón de inyección existente).

A) **Inyección explícita como los existentes**: `create_app` crea `CycleCounter`, se lo pasa a `DiscoveryTrigger(..., counter=...)` y a `collect(..., cycles=...)` — mismos seams que `ApiRequestCounter`, testeable sin red *(recomendado)*

B) Contador global de módulo (`core.metrics._CYCLES`) — estado oculto, difícil de aislar entre tests

C) Contador persistido en `discovery_runs` (ya guarda el estado; doble fuente de verdad)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Gate de cobertura de `discovery/` en CI (Logical Components)

Contexto: NFR-U4-MNT-01 fija ≥70% en `discovery/`; el CI ya tiene un step separado para el gate `gui/` (espejo natural).

A) **Step de CI separado** `Discovery coverage gate` con `coverage report --include='*/discovery/*' --fail-under=70`, idéntico en forma al gate `gui/` (fallas localizadas, mensajes claros) *(recomendado)*

B) Unificar gates (`core`, `gui`, `discovery`) en un solo comando con `--fail-under` global más alto (un fallo no dice qué paquete)

C) Solo el gate global 70% (sin step propio — incumple NFR-U4-MNT-01)

D) Other (describe después de `[Answer]:`)

[Answer]: A
