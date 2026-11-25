# NFR Design Patterns — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — NFR Design (Parte 2: Generation)
**Fecha**: 2026-11-18
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/`
**Decisiones (plan Q1–Q7)**: **A en todas** — loop continúa tras ventana fallida (sin circuit breaker); guard de emisión monótono ante salto de reloj; pipeline síncrono de un solo hilo; eventos `dataclass` ligeros con Pydantic solo en la frontera de export; datos del feed validados por contrato U1 + logs JSON; inyección por constructor con defaults reales; gate de cobertura como step de CI separado.
**Entradas**: `nfr-requirements/*` (NFR-U5-*, TS-U5-01..13), Functional Design de U5 (BR-U5-01..36, D-U5-01..09), `foundation` (retry, logging, models).

---

## 1. Patrones de Resilience

### P1 — Fallos por ventana en el `--loop` (→ NFR-U5-AVAIL-01/02, Q1=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Una ventana fallida (export agotado tras ×5, o fuente caída) se registra (`event=sensor_export_failed` \| `sensor_source_error` + causa) y el worker **procede a la siguiente ventana**; los fallos son **por ventana**, sin estado acumulado entre ventanas, **sin circuit breaker** ni contador de fallos consecutivos |
| `--once` | Una sola ventana ⇒ exit 1 ante fallo (BR-U5-29) — la gestión de reinicio la tiene K8s (Deployment `restartPolicy` de U9) |
| SIGTERM | Se atiende **entre** ventanas (nunca a mitad de un POST en tránsito) — AVAIL-02 |
| No hace | Sin persistencia de estado (worker sin BD); sin backoff entre ventanas (la siguiente ventana llega en ≤ W s); sin alertas propias (sin `/metrics`, MNT-04) |
| Verificación | Test de loop con cliente que falla 2 ventanas: ambas se intentan, el worker sigue vivo, la tercera ventana se emite; `test_cli -k exit_codes` |

### P2 — Guard de emisión monótono ante regresión de reloj (→ Q2=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | El worker guarda `last_emitted_window_start`; si el `window_start = floor(now/W)*W` calculado es **≤ último emitido** (ajuste NTP hacia atrás), la ventana **no se emite**: se descarta el acumulador con `log warning event="window_clock_regression"` y se espera al siguiente borde |
| Por qué | Protege el `window_id` determinista (uuid5, D-U5-02) de repetirse y evita "ventanas viajeras" en el Core/Prometheus (que comparan timestamps UTC) |
| No hace | Sin re-sincronización forzada ni salto de reloj propio; sin doble emisión "por si acaso" (el dedup de U2 no es el mecanismo de defensa — el guard lo es) |
| Verificación | `test_worker -k clock_regression` con reloj falso que retrocede ⇒ sin segunda emisión del mismo `window_start` + warning en log |

### P3 — Degradación por capas (heredada de NFR-U5-AVAIL-01/02, sin pregunta)

| Elemento | Diseño |
|---|---|
| Mecanismo | (a) fuente lanza a mitad de ventana ⇒ `sensor_source_error`, acumulador descartado, loop continúa (AVAIL-01); (b) Core caído ⇒ `with_retries` ×5 (backoff 0.5·2ⁿ ± jitter) ⇒ ventana/chunk descartado con `sensor_export_failed`, loop continúa (D-U5-05); (c) config inválida ⇒ `ConfigError` al arranque (fail-fast, fuera del loop) |
| Orden | El fallo **nunca** deja el worker "colgado": cada ventana termina emitida, descartada con log, o abortada con log — y el ciclo siguiente arranca |
| Verificación | `test_worker -k source_error_continues` + `-k retry_exhausted_drop`; `test_config -k invalid_config` |

---

## 2. Patrones de Performance

### P4 — Pipeline síncrono de un solo hilo (→ NFR-U5-PERF-01, Q3=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Un solo hilo ejecuta: iterar `PacketSource` → acumular → al borde cerrar ventana → proyectar → exportar (chunked) → esperar al siguiente borde; sin colas, sin hilos de fondo, sin `asyncio` |
| Por qué | Determinista (mismo orden de eventos ⇒ mismo lote ⇒ dedup estable), sin carrera entre colección y export, suficiente para el MVP: con `W ≥ 1 s` y POST local el bloqueo del export es ms en el caso normal (retries largos = caso de fallo, ventana ya aceptada como descartable) |
| Límite documentado | En la **captura real futura**, un export con retries podría superar W y dejar un hueco de colección; la mejora documentada (buffer de eventos o export en hilo de fondo con cola ordenada) queda en domain-entities §5 — sin implementar en el MVP |
| No hace | Sin thread pool en el sensor; sin prioridad de colección sobre export; sin buffer circular |
| Verificación | Test de 5 ventanas con reloj falso y MockTransport: orden de POSTs secuencial y sin solapes; baseline informativo de throughput (PERF-01) |

### P5 — Eventos ligeros + Pydantic en la frontera (→ NFR-U5-TECH-01, Q4=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `IpPacket`/`ArpPacket` son `dataclass` (slotted) internos — **cero validación Pydantic por evento**; los acumuladores usan `dict`/contadores O(1) (`packets_by_protocol`, `bytes_by_protocol`, `pairs_by_protocol`); al cierre se proyecta **una vez por observación** a `TrafficObservation`/`ArpObservation` (Pydantic U1, `extra="forbid"`) antes del POST |
| Por qué | El hot path de GT-04 (rate alto) no paga validación por paquete; la seguridad/validez se garantiza igual en la frontera de contrato (SEC-03, Q5) — validación donde exporta, no donde acumula |
| No hace | Sin dicts crudos sin tipar en la proyección (siempre contrato U1); sin validación por evento "por si acaso" |
| Verificación | Test de throughput informativo (PERF-01); test de frontera: proyección con campo inválido ⇒ `ValidationError` antes del POST; revisión de `dataclass` en `source.py` |

---

## 3. Patrones de Security

### P6 — Confianza cero en datos del feed (→ NFR-U5-SEC-03, Q5=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Todo evento cruza la frontera de contrato al cierre de ventana: `IpPacket`/`ArpPacket` → **`TrafficObservation`/`ArpObservation` (Pydantic U1)** antes del POST — IPs/MAC canónicos, longitudes ≤255, rangos `ge=0`, `Literal` de protocolo/opcode, `extra="forbid"` (sin payload); los logs son **JSON estructurado** (`foundation.logging`) con campos separados ⇒ el contenido del feed nunca se interpreta como formato de log (sin log injection) |
| No hace | Sin sanitización extra de control chars (los campos son tipados y acotados); sin escaping agresivo; sin cifrado del lote (transporte heredado HTTP + NetworkPolicy de U9, como U2/U4) |
| Verificación | Test: evento con string hostil en `interface`/campos libres ⇒ `ValidationError`/recorte del modelo U1, jamás en el POST; test de log: payload JSON con `event` canónico y sin token |

### P7 — Sin privilegios en el MVP (heredado de NFR-U5-SEC-01, sin pregunta)

| Elemento | Diseño |
|---|---|
| Mecanismo | El paquete no abre sockets crudos, no importa `scapy`, no exige capabilities: `SimulatedSource`/`FixtureSource` puros; imagen **non-root** (NFR-SEC-02); el diseño de captura real (AF_PACKET + `hostNetwork` + `CAP_NET_RAW/NET_ADMIN` + OQ-01 `CAP_SYS_ADMIN`) queda documentado para U9 |
| Verificación | `grep -r scapy src/` vacío; `requirements.txt` sin cambios; Dockerfile `USER` no-root (existente) |

### P8 — Config estricta y secretos mínimos (heredado de NFR-U5-SEC-02, sin pregunta)

| Elemento | Diseño |
|---|---|
| Mecanismo | `TrafficSettings` (`frozen`, `extra="forbid"`): claves `SENTINEL_TRAFFIC_*` desconocidas ⇒ `ConfigError`; ventana ∈ {1,5,10,30,60}; `fallback=false` ⇒ `ConfigError` (D-U5-07); único secreto = `SENTINEL_INGEST_TOKEN` (hereda comparación constante de U2), nunca en logs |
| Verificación | `test_config -k strict_env / -k window_values / -k fallback_false_rejected`; test de log sin token |

---

## 4. Patrones de Maintainability

### P9 — Seams de inyección por constructor (→ NFR-U5-MNT-02, Q6=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `run_window(settings, source, client, clock, …)` con **defaults reales** en producción (`SimulatedSource`, `IngestClient` httpx, reloj UTC, `load_traffic_settings()`); los tests construyen: `FixtureSource` + `httpx.Client(transport=MockTransport)` + `FakeClock` + `TrafficSettings` de test |
| Por qué | Cero monkeypatch de módulos (tests estables ante refactor), cero `sleep` (reloj falso), mismo espíritu que los seams de `create_app` en U2/U3/U4 |
| No hace | Sin contenedor DI/registry; sin variables globales de módulo para fuente/cliente/reloj |
| Verificación | Test de ventana completa con los 4 seams inyectados sin red ni sleep; revisión de firmas con defaults |

### P10 — Logging canónico sin métricas propias (→ NFR-U5-MNT-04, heredado)

| Elemento | Diseño |
|---|---|
| Mecanismo | `foundation.logging` con `component=traffic.*` y eventos canónicos snake_case (`arp_rate`, `sensor_export_failed`, `sensor_source_error`, `window_clock_regression`); el sensor **no** expone `/metrics` ni define familias — R-02/R-04 usarán las familias de U1 vía U7 |
| Verificación | Test de log JSON (campos `event`/`component`); revisión: sin servidor de métricas ni `METRIC_FAMILIES` nuevo en U5 |

### P11 — Gate de cobertura como step separado (→ NFR-U5-MNT-01, Q7=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | Job `test` de `ci.yml`: paso propio `Traffic coverage gate` ⇒ `coverage report --include='*/traffic/*' --fail-under=70` sobre el **mismo** `.coverage` (espejo exacto de los gates `gui/` y `discovery/`; ~0 s, sin re-ejecutar tests) |
| No hace | Sin segunda invocación de pytest; sin gate unificado que oculta el paquete culpable |
| Verificación | El step está presente en `ci.yml`; en local el mismo comando pasa con `traffic/` ≥70 |

### P12 — PBT de agregación de ventanas (→ NFR-U5-MNT-03, Q8 NFR-Req=A)

| Elemento | Diseño |
|---|---|
| Mecanismo | `tests/property/test_window_aggregation.py` con `hypothesis`: (a) las ventanas particionan la línea temporal sin solapes ni huecos, (b) Σ `packet_length_bytes` de los grupos == Σ bytes de los eventos de la ventana, (c) mismo `(seed, rate)` ⇒ mismas observaciones |
| Verificación | `pytest tests/property/test_window_aggregation.py` en job `test` (junto a los PBT de U1/U2/U4) |

---

## 5. Patrón de Scalability (cerrado — sin pregunta)

### P13 — Chunking ≤1000, pairs ≤100, single-sensor (→ NFR-U5-SCAL-01, heredado)

| Elemento | Diseño |
|---|---|
| Mecanismo | Los items de una ventana se parten en POSTs secuenciales de ≤1000 (`MAX_BATCH_ITEMS`) — ráfaga ARP jamás produce 422; `pairs` acotado a 100 por observación; MVP de **un solo sensor** (NFR-AVAIL-01) |
| Crecimiento | Multi-sensor (`sensor_id` ya reservado), HA o >1 ventana concurrente se revisa en **U11** (misma bar que NFR-U2-SCAL-01/U3/U4): sin cambio de diseño hoy |
| Verificación | `test_client -k chunked_export` (2500 ARP ⇒ 3 POSTs); `test_aggregation -k pairs_cap` |

---

## 6. Trazabilidad de patrones → NFR

| NFR (U5) | Patrón |
|---|---|
| NFR-U5-PERF-01 | P4 (pipeline síncrono; baseline informativo en tests de code-gen) |
| NFR-U5-SCAL-01 | P13 |
| NFR-U5-AVAIL-01/02 | P1, P3 |
| NFR-U5-REL-01 | P2 (guard monótono) + reloj inyectable (P9) |
| NFR-U5-SEC-01 | P7 |
| NFR-U5-SEC-02 | P8 |
| NFR-U5-SEC-03 | P6 |
| NFR-U5-MNT-01 | P11 |
| NFR-U5-MNT-02 | P9 |
| NFR-U5-MNT-03 | P12 |
| NFR-U5-MNT-04 | P10 |
| NFR-U5-TECH-01..04 | P5 (TECH-01/03), P4+P9 (TECH-04), config estricta heredada (FD §3.1) |
