# NFR Design Plan — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — NFR Design (Parte 1: Planning)
**Fecha**: 2026-11-18
**Estado**: GENERATED — respuestas todas A (2026-11-18); artefactos generados; pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/`
**Entradas**: `construction/u5-traffic/nfr-requirements/*` (aprobado 2026-11-18T18:20:14Z: NFR-U5-PERF/SCAL/AVAIL/REL/SEC/MNT/TECH, TS-U5-01..13), Functional Design de U5 (aprobado), `nfr-design` de U2/U3/U4 (patrones de referencia), `foundation` (retry/logging/models).

---

## 1. Contexto del assessment (Step 1 — analizado)

Cómo incorporar los NFR aprobados de U5 en **patrones de diseño y componentes lógicos** concretos: qué pasa con el `--loop` cuando falla una ventana o salta el reloj, si la exportación bloquea la colección de eventos (throughput NFR-PERF-02), cómo representar los eventos del hot path sin validar Pydantic por paquete, cómo tratar datos no confiables del feed hacia logs/persistencia, y cómo se inyectan/testean fuente, cliente y reloj (seams) + wiring del gate de cobertura en CI.

Ya decidido en etapas previas (NO se pregunta): chunking ≤1000 (SCAL-01), fallo de fuente ⇒ ventana abortada/loop vivo (AVAIL-01), descarte de ventana tras retries sin buffer (D-U5-05), reloj UTC inyectable (REL-01), sin privilegios/scapy en MVP (SEC-01), config estricta (SEC-02), sin payload/token en logs (SEC-03), gate `traffic/` ≥70% (MNT-01), tests sin red/sockets (MNT-02), PBT de agregación (MNT-03), logging canónico sin `/metrics` propio (MNT-04), cero deps pip (TECH-01), determinismo del simulador (TECH-03), CLI `--once/--loop` (TECH-04), sin circuit breaker planteado aún (ver Q1).

**Categorías evaluadas** (todas las obligatorias):

| Categoría | Aplica a U5 | Tratamiento |
|---|---|---|
| Resilience Patterns | Sí | Q1 (continuidad del `--loop` tras ventana fallida), Q2 (salto de reloj hacia atrás) |
| Scalability Patterns | Cerrado | **Sin pregunta**: SCAL-01 (chunking ≤1000) + `pairs` ≤100 + single-sensor MVP (NFR-AVAIL-01) ya fijados; crecimiento multi-sensor/HA se revisa en U11 (misma bar que U2/U3/U4) |
| Performance Patterns | Sí | Q3 (pipeline síncrono vs export en background), Q4 (eventos ligeros + Pydantic solo en la frontera) |
| Security Patterns | Sí | Q5 (datos no confiables del feed → contrato U1 + logs JSON); transporte heredado de U2 (HTTP plano + NetworkPolicy de U9) sin mitigación extra en U5 |
| Logical Components | Sí | Q6 (seams de inyección: source/client/clock por constructor), Q7 (gate de cobertura como step de CI) |

---

## 2. Checklist del plan

- [x] Analizar NFR requirements aprobados
- [x] Generar preguntas de diseño NFR (Q1–Q7)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-18: "Acepto todo" ⇒ Q1–Q7 = A)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; interacciones revisadas (Q1×Q3 (sync+retries ⇒ loop vivo), Q2×FD window_id uuid5, Q4×SEC-03 contrato frontera, Q6×FD reloj inyectable) ⇒ **sin FQ necesarias**
- [x] Generar `nfr-design/nfr-design-patterns.md`
- [x] Generar `nfr-design/logical-components.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño NFR

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Continuidad del `--loop` tras una ventana fallida (Resilience Patterns)

Contexto: NFR-U5-AVAIL-01 fija que la fuente no mata el loop; el export puede fallar igual (Core caído tras retries ×5 ⇒ ventana descartada, D-U5-05). En `--loop` (demo/Deployment U9) el worker debe seguir vivo hasta SIGTERM para mantener el heartbeat.

A) **El loop continúa**: la ventana fallida se registra (`event=sensor_export_failed` + causa) y el worker procede a la siguiente ventana — fallos **por ventana**, sin estado acumulado, sin circuit breaker ni contador de fallos consecutivos; SIGTERM se atiende **entre** ventanas *(recomendado)*

B) **Circuit breaker ligero**: tras N (p. ej. 3) ventanas fallidas consecutivas, el worker sale con exit 1 para que K8s gestione el reinicio

C) Parar el loop en el primer fallo de export (fail-fast total, como `--once`)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Salto de reloj hacia atrás (Resilience Patterns)

Contexto: las ventanas son epoch-aligned UTC (BR-U5-12); un ajuste NTP hacia atrás puede hacer que `floor(now/W)*W` produzca un `window_start` **ya emitido** ⇒ mismo `window_id` (uuid5) y posibles ventanas duplicadas/repetidas.

A) **Guard de emisión monótona**: `last_emitted_window_start`; si el `window_start` calculado ≤ último emitido ⇒ **no se emite** (se descarta el acumulador con `log warning event="window_clock_regression"` y se espera al siguiente borde); el reloj en tests controla el caso *(recomendado)*

B) Emitir igual (el dedup de U2 absorbe el duplicado por contenido; acepta una ventana "repetida" en el log)

C) Resetear el acumulador y re-alinear sin guardar el último emitido (pierde la protección)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Pipeline síncrono vs export en background (Performance Patterns)

Contexto: NFR-U5-PERF-01 apunta a ≥10k flows/s (no vinculante); un `POST` con retries puede tardar hasta ~15 s (5 intentos con backoff); con ventanas de 1 s, la exportación bloqueante dejaría huecos de colección (en el MVP simulado los eventos se generan al iterar — sin pérdida real; en la captura futura sí importaría).

A) **Pipeline síncrono de un solo hilo** (colecciona → cierra ventana → exporta → siguiente); con `W ≥ 1 s` y POST local el hueco es ms; la posibilidad de perder eventos durante un export largo en la **captura real futura** queda documentada en §5 (mejora: buffer/async) — determinista y simple para el MVP *(recomendado)*

B) **Hilo de export en background** con cola de ventanas cerradas (la colección nunca se bloquea; añade ordenación, shutdown y testing de concurrencia)

C) `asyncio` end-to-end (reescritura del worker; sin beneficio con fuente síncrona)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Representación del hot path de eventos (Performance Patterns)

Contexto: a SIM_RATE alto (GT-04) hay cientos/miles de eventos por ventana; validar Pydantic **por evento** (aunque sea el modelo interno) cuesta en el camino caliente; los contratos U1 ya validan en la frontera de export (por observación, no por paquete).

A) **Eventos ligeros + Pydantic en la frontera**: `IpPacket`/`ArpPacket` como `dataclass` slotted (o NamedTuple) internos sin validación por evento; los acumuladores usan `dict`/contadores O(1); la validación Pydantic ocurre **una vez por ventana** al proyectar `TrafficObservation`/`ArpObservation` (contratos U1) antes del POST *(recomendado)*

B) Pydantic (`extra="forbid"`) en cada evento de la fuente (validación constante, más lento en el hot path)

C) Dicts crudos sin tipar en todo el pipeline (sin validación en ninguna frontera — incumple SEC-03)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Datos no confiables del feed hacia logs y persistencia (Security Patterns)

Contexto: los eventos (simulados hoy, de red real mañana) alimentan logs y contratos U1; SEC-03 cubre "sin payload", pero no el contenido de strings/tipos no confiables (log injection, valores fuera de rango).

A) **Validación en el contrato + JSON estructurado**: al cierre de ventana todo se convierte a `TrafficObservation`/`ArpObservation` de U1 (Pydantic: IPs/MAC canónicos, longitudes ≤255, rangos `ge=0`, `Literal` de protocolo/opcode) **antes** del POST; los logs son JSON con campos separados (`foundation.logging`) ⇒ el contenido del feed nunca se interpreta como formato de log; sin sanitización extra *(recomendado)*

B) Sanitización explícita además de Pydantic (strip de control chars en interfaces/strings)

C) Escapado agresivo/truncado de todo string no alfanumérico

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Seams de inyección para tests (Logical Components)

Contexto: MNT-02 exige tests sin red/sockets/sleep; el worker depende de fuente, cliente HTTP, reloj y settings; FD ya promete reloj y fuente inyectables.

A) **Inyección por constructor en todo el ensamblaje**: `run_window(settings, source, client, clock, …)` con **defaults reales** para producción; los tests construyen con `FixtureSource` + `httpx.MockTransport` + `FakeClock` + settings de test — sin monkeypatch de módulos ni `sleep` *(recomendado)*

B) Defaults globales + monkeypatch de `source.py`/`client.py`/`datetime` en tests (menos código de producción, tests frágiles)

C) Factory con registro/lookup (DI container — peso innecesario para lab)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Gate de cobertura de `traffic/` en CI (Logical Components)

Contexto: NFR-U5-MNT-01 fija ≥70% en `traffic/`; el CI ya tiene steps separados para los gates `gui/` y `discovery/` (espejo natural).

A) **Step de CI separado** `Traffic coverage gate` con `coverage report --include='*/traffic/*' --fail-under=70`, idéntico en forma a los gates anteriores (fallas localizadas, mensajes claros) *(recomendado)*

B) Unificar todos los gates (`core`, `gui`, `discovery`, `traffic`) en un solo comando (un fallo no dice qué paquete)

C) Solo el gate global 70% (sin step propio — incumple NFR-U5-MNT-01)

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Follow-up (Step 5 — ambigüedad detectada)

> Análisis de interacciones Q1×Q3 (pipeline síncrono: el fallo de export no mata el loop — P1), Q2×FD (guard monótono protege el `window_id` uuid5), Q4×SEC-03 (validación por ventana en la frontera U1), Q6×FD (seams ya prometidos): todas resueltas por A. **Sin follow-ups.**
