# Functional Design Plan — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — Functional Design (Parte 1: Planning)
**Fecha**: 2026-11-18
**Estado**: GENERATED — Q1–Q13 = A (2026-11-18); artefactos FD generados; pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/` (fuente de paquetes abstracta + simulada, agregación de ventanas, ARP request/reply, export al Core)
**Entradas**: `unit-of-work.md` (§U5), `unit-of-work-story-map.md` (ST-M3-01..06, todas documented-only), `stories.md` (AC), `requirements.md` (FR-TRAF-01..05, FR-ARP-01..04, NFR-AVAIL-01, NFR-SEC-02, NFR-TECH-02/03), `component-methods.md` (§11 Colectores, §36 `ingest_traffic`), `services.md` (§2.1, health/heartbeat), `components.md` (C10 Traffic Sensor), `implementation-scope.md` (M3: fallback simulado/fixtures; captura real documentada), `demo-plan.md` (GT-04/GT-05), contratos de U1+U2 aprobados (`TrafficObservation`, `ArpObservation`, `Batch` con discriminador `source`, `POST /api/v1/ingest`, `HealthService.sensor_heartbeats`, `InventoryService.observe` con detección `ARP_MAPPING_CHANGED`).

---

## 1. Contexto de la unidad (Step 1 — analizado)

- **Responsabilidad**: capturar metadatos IP/ARP (diseño SPAN/mirror **documentado**), agregar en ventanas (1/5/10/30/60 s, default 5), calcular tasa de mensajes ARP, tracking IP↔MAC, enviar agregados al Core por HTTP; heartbeats de disponibilidad para U6/U8.
- **Alcance construido (implementation-scope)**: **fuente de paquetes abstracta + fallback simulado/fixtures** para GT-04/GT-05; la **captura real AF_PACKET queda documentada**, no demostrada. Las historias ST-M3-01..06 son **documented-only**; el simulador/fixtures es **código de soporte de la unidad**.
- **Frontera**: no persiste en SQLite, no expone `/metrics`, no evalúa umbrales, no almacena payload, no modifica paquetes; solo `foundation` + HTTP hacia el Core (mismo patrón que U4).
- **Depende de**: U1 (modelos `TrafficObservation`, `ArpObservation`, `Batch`, `with_retries`), U2 (`POST /api/v1/ingest` con Bearer, dedup por `dedup_key`, `sensor_heartbeats` derivado de `MAX(observed_at)` por `sensor_id`, `InventoryService` → evento `ARP_MAPPING_CHANGED` al cambiar MAC).
- **Lo que U2 NO hace y U5 debe diseñar**: fuente de paquetes (real/simulada), agregación por ventanas, parseo ARP, cálculo de tasa ARP, cliente de export con reintentos, configuración `SENTINEL_TRAFFIC_*`, CLI/entrypoint `python -m sentinel.traffic`, generador determinista para GT-04/GT-05.
- **Facts relevantes**: `Batch.reconcile` solo aplica si hay `DiscoveryObservation` (lotes de sensor ⇒ `has_discovery=False` ⇒ sin reconcile); ARP con IP desconocida **no crea activo** (`create_if_missing=False` para no-discovery); `Protocol = tcp|udp|icmp|arp|other` (ARP va en `ArpObservation`, no en traffic); `FlowPair = {src_ip, dst_ip}` (sin conteos); `pairs` limitado a `MAX_BATCH_ITEMS=1000`; ST-M3-03 AC cita ruta `/ingest/traffic` (hoy solo existe `/ingest`); ST-M3-02 AC2 cita `helm lint --set traffic.window=7s` (chart llega en U9); OQ-01 (`CAP_SYS_ADMIN`) es pregunta NFR/Infra.
- **Categoría Frontend**: **no aplica** a U5 (sin UI).

---

## 2. Checklist del plan

- [x] Analizar unidad, historias y restricciones
- [x] Generar preguntas de diseño funcional (Q1–Q13)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-18: "Acepto todo" ⇒ Q1–Q13 = A)
- [x] Analizar respuestas y resolver ambigüedades — interacciones revisadas (Q3×Q13 simulador+fixtures; Q4×Q6 heartbeat; Q10×Q11 ARP delegado en U2; Q7×Q10 sin cambio U1/U2) ⇒ **sin FQ necesarias**
- [x] Generar `business-logic-model.md`, `business-rules.md`, `domain-entities.md` en `construction/u5-traffic/functional-design/`
- [ ] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño funcional

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Estructura del paquete y frontera de imports

Contexto: U1 ya documenta `python -m sentinel.traffic` en el Dockerfile; U4 creó el precedente `src/sentinel/discovery/` con frontera estricta (solo `foundation` + HTTP, sin `sentinel.core`/`sqlite3`); `unit-of-work.md` prohíbe persistir y evaluar umbrales.

A) **`src/sentinel/traffic/` espejo de discovery**: `config.py` (loader `SENTINEL_TRAFFIC_*`), `source.py` (protocolo + fuente simulada), `aggregator.py` (ventanas), `arp.py` (parseo + tasa), `client.py` (`POST /api/v1/ingest` con retries), `worker.py` (ciclo ventana→export), `__main__.py` (CLI); tests en `tests/unit/traffic/` + `tests/integration/`; frontera: solo `foundation` + httpx, sin `sentinel.core`, sin `sqlite3`, sin `scapy` *(recomendado)*

B) Estructura plana en `src/sentinel/traffic.py` (un solo módulo)

C) Reutilizar módulos de `sentinel.discovery` (config/client compartidos entre unidades)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Fuente de configuración y validación de la ventana

Contexto: los Helm values llegan en U9; `CoreSettings` de U1 no admite claves nuevas; ST-M3-02 AC2 exige rechazar ventanas no soportadas (hoy verificable en el loader, el `helm lint` llega con U9); U4 usó loader estricto `SENTINEL_DISCOVERY_*`.

A) **Variables de entorno propias** `SENTINEL_TRAFFIC_*`: `WINDOW_SECONDS` (default 5; solo `{1,5,10,30,60}`; otro ⇒ `ConfigError`), `INTERFACE` (default `eth0`), `SENSOR_ID` (default `sensor-0`), `SIM_SEED`/`SIM_RATE`/`FALLBACK` (Q13), `SENTINEL_API_BASE` + `SENTINEL_INGEST_TOKEN` (compartidos con U4); loader estricto en `traffic/config.py`; `CoreSettings` intacto *(recomendado)*

B) Solo CLI args (`--window`, `--interface`…), sin variables de entorno

C) Archivo YAML/JSON montado como volumen

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Abstracción de fuente de paquetes y alcance de la captura real

Contexto: FR-TRAF-01 (AF_PACKET/TPACKET_V3) + NFR-TECH-02 (scapy en el stack) vs `implementation-scope.md` ("la captura real queda documentada"); U5 debe poder correr en CI/demo sin caps ni red real; los tests usan fixtures (frontera de la unidad).

A) **Protocolo `PacketSource`** (iterador de eventos tipados `IpPacket | ArpPacket` con `observed_at, interface, …`); **implementado**: `SimulatedSource` (fixtures JSON versionados + generador); **solo documentado** en el FD: `AfPacketSource` (diseño scapy sobre AF_PACKET, sin código); **sin dependencia scapy** en `requirements.txt` *(recomendado)*

B) scapy como dependencia real con `AfPacketSource` implementado (tests lo mockean; ejecución real requiere caps/root y queda fuera de CI)

C) Solo fixtures estáticos (sin generador sintético ni protocolo abstracto)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Semántica de las ventanas de agregación (FR-TRAF-04, ST-M3-02)

Contexto: ST-M3-02 AC1: 25 s con ventana 5 s ⇒ cinco ventanas con `bytes_per_second` sobre duración efectiva; `HealthService` deriva heartbeats de `MAX(observed_at)` por `sensor_id` (cualquier observación sirve de latido); GT-05 = "detener heartbeat simulado".

A) **Tumbling windows alineadas al reloj** (`window_start = floor(now/W)*W`); emisión **al cierre** de cada ventana; **toda ventana se emite aunque esté vacía** (`packets=0`, `bytes_per_second=0`) — las ventanas **son el heartbeat** (red idle ≠ sensor caído; GT-05 = detener el loop) *(recomendado)*

B) Mismo esquema, pero solo se emiten ventanas con ≥1 paquete (cero ruido; en red idle el heartbeat cae y R-04 podría dispararse en falso)

C) Ventanas no alineadas (desde el arranque del proceso)

D) Sliding windows

E) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Granularidad del `TrafficObservation` y pares (modelo U1)

Contexto: el modelo U1 tiene `protocol` **singular**, `pairs: list[FlowPair]` (solo `src_ip/dst_ip`), `window_id` opcional, límite `MAX_BATCH_ITEMS=1000`; FR-TRAF-03 extrae solo campos mínimos (sin MAC/puerto/payload).

A) **1 `TrafficObservation` por (ventana × interfaz × protocolo ∈ {tcp,udp,icmp,other})**: `packets`, `packet_length_bytes` (suma), `bytes_per_second = suma / duración_efectiva`, `flows` = nº de pares distintos, `pairs` = pares distintos **acotados a 100** (config); `window_id` **determinista** `uuid5(sensor_id, window_start, interface, protocol)` para trazabilidad/reintentos *(recomendado)*

B) 1 por ventana × interfaz (mezcla protocolos — no encaja con `protocol` singular)

C) 1 por par src-dst (alta cardinalidad; el modelo ya agrupa en `pairs`)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Cadencia de export y heartbeats (FR-TRAF-05, ST-M3-03, GT-05)

Contexto: `component-methods.md` §11 `post_batch` reintenta "hasta obtener respuesta"; `HealthService` ya calcula `sensor_heartbeats`; ST-M7-04 alerta `sentinel_collector_up{collector="traffic"}==0` (métrica de U7 futura, derivada de observaciones).

A) **1 `POST /api/v1/ingest` por ventana cerrada** (lote mixto: `TrafficObservation` + `ArpObservation` de esa ventana); cadencia = ventana (default 5 s); **sin endpoint de latido propio**: las observaciones con `sensor_id` son el heartbeat; GT-05 = detener el loop *(recomendado)*

B) Heartbeat dedicado con intervalo propio (endpoint nuevo en U2)

C) Acumular N ventanas antes de exportar (lotes menos frecuentes)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Contrato de ingesta hacia U2 (component-methods §36 vs código real)

Contexto: ST-M3-03 AC1 cita `POST /api/v1/ingest/traffic` → `202`, pero U2 construyó el endpoint genérico `POST /api/v1/ingest` con `Batch` (discriminador `source`) que **ya acepta** `traffic`/`arp`; las historias M3 son documented-only; `component-methods.md` esquematiza `ingest_traffic(batch)`.

A) **Reutilizar `POST /api/v1/ingest` + `Batch` sin editar U2**: las firmas de component-methods se interpretan como el proceso genérico ya implementado; la ruta `/ingest/traffic` del AC queda documented-only junto con la historia *(recomendado)*

B) Añadir alias `POST /api/v1/ingest/traffic` en U2 (edición acotada) que acepte `Batch` con items traffic/arp — cumple el AC literal

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — Cliente HTTP del sensor

Contexto: `discovery/client.py` (U4) ya hace `POST /ingest` con Bearer + `with_retries` ×5; no existe paquete compartido; frontera de unidades prohíbe que U5 importe de `sentinel.discovery`.

A) **`traffic/client.py` espejo** de `discovery/client.py` (httpx + `foundation.retry` ×5, Bearer `SENTINEL_INGEST_TOKEN`, base `SENTINEL_API_BASE` default loopback; sin `reconcile` explícito — los lotes de sensor no llevan discovery) *(recomendado)*

B) Importar `sentinel.discovery.client.IngestClient` desde U5 (acoplamiento entre unidades)

C) Refactor: mover el cliente a un paquete común (edita U4 ya aprobado)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Manejo de fallo del Core durante el export (services.md §2.1)

Contexto: services.md pide "reintenta con backoff hasta lograrlo"; U4 eligió ×5 y después marcar el ciclo `failed` (D-U4-03); NFR-AVAIL-01 acepta hueco de visibilidad si el sensor está solo; no hay requisito de buffer local.

A) **`with_retries` ×5 con backoff** (mismo patrón U4); agotado ⇒ log estructurado `sensor_export_failed` + **se descarta la ventana** y el loop continúa con la siguiente (sin buffer local; gap documentado) *(recomendado)*

B) Buffer local en disco + reintento al recuperar el Core (complejidad nueva sin requisito)

C) Reintento infinito hasta lograr respuesta (puede atrasar ventanas siguientes; literal de services.md)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 10 — Dónde se calcula y vive la tasa ARP (FR-ARP-03, ST-M3-05)

Contexto: ST-M3-05 AC1 exige `arp_messages_per_second = 10` verificable con `pytest tests/unit/test_arp_rate.py` (función de dominio testeable en U5); `ArpObservation` es **por mensaje** (sin campo de tasa); U1 define el catálogo `sentinel_arp_messages_total` (U7 lo expondrá); R-02 es regla de Prometheus (U8, documentada); editar modelos U1 tiene costo de regresión.

A) **Cálculo en U5 como función pura** `arp_rate(counts, window_seconds) -> float` por (ventana × interfaz), testeable según el AC; el valor se registra en **log estructurado** del sensor; la persistencia sigue siendo `ArpObservation` crudas y U7 expondrá `sentinel_arp_messages_total` (+ PromQL `rate()`) para R-02 — **sin cambio de modelos U1** *(recomendado)*

B) Edición acotada U1: nuevo modelo `ArpWindow` (ventana × interfaz × tasa) persistido por U2 (más alcance en U1+U2)

C) Reutilizar `TrafficObservation` con `protocol="arp"` para exportar la tasa (abusa del contrato)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 11 — Tracking IP↔MAC y detección de cambio (FR-ARP-02/04, ST-M3-04/06)

Contexto: `unit-of-work.md` lista "tracking IP↔MAC" en U5, **pero** U2 ya lo implementa: `InventoryService.observe` con `hwsrc` detecta `mac_changed` ⇒ evento `ARP_MAPPING_CHANGED` (`service.py`); ST-M3-04/06 AC se pueden verificar con un integration test de ingest con MAC cambiado; la alerta R-03 es documented-only (U8).

A) **Delegación documentada**: U5 solo parsea y exporta `ArpObservation` (request opcode 1 y reply opcode 2, campos `psrc/pdst/hwsrc/hwdst/interfaz/sensor_id`); el **estado y la detección viven en U2** (ya generado); el FD registra la delegación y el plan de tests incluye integration test de cambio de MAC vía ingest *(recomendado)*

B) Doble tracking: U5 además mantiene mapa local `ip→mac` por interfaz para log/alerta local (duplica estado)

C) Mover la detección de U2 a U5 (rework de U2 aprobado)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 12 — Modos de ejecución del CLI (entrypoint, U9 futuro)

Contexto: el Dockerfile de U1 ya documenta `python -m sentinel.traffic`; U9 desplegará el sensor como Deployment (C10); los tests y la demo sin chart necesitan dispararlo; U4 usó `--once`/`--loop`.

A) **CLI con dos modos**: `--once` (una ventana completa y sale; tests/CI) y `--loop` (demo y Deployment de U9; duerme hasta el borde de ventana); ambos comparten el mismo worker *(recomendado)*

B) Solo `--loop`

C) Solo `--once` (un orquestador externo lo invoca)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 13 — Generador para GT-04 (tráfico alto) y GT-05 (sensor caído)

Contexto: demo-plan.md exige "nunca improvisar datos en vivo; usar fixtures y declarar que son simulados"; GT-04 = provocar tráfico alto ⇒ R-01; GT-05 = detener heartbeat ⇒ R-04; los tests necesitan reproducción exacta.

A) **`SimulatedSource` con generador determinista**: `SIM_SEED` (default fijo; reproducible) + `SIM_RATE` (paquetes/s, default moderado; **GT-04 = subir la tasa vía env**) + **fixtures JSON versionados** para unit tests; **GT-05 = detener el loop** del sensor *(recomendado)*

B) Solo fixtures fijos (GT-04 = ingerir un fixture "high traffic" una vez, sin generador)

C) Tráfico real del laboratorio para GT-04 (depende de visibilidad SPAN — frágil y fuera del alcance construido)

D) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Follow-up (Step 5 — ambigüedad detectada)

> Análisis de interacciones Q3×Q13, Q4×Q6, Q7×Q10, Q10×Q11, Q1×Q8: todas resueltas por las respuestas A (simulador determinista sin scapy; ventanas = heartbeat; sin ediciones U1/U2; cliente espejo). **Sin follow-ups.**

---

## 5. Artefactos a generar (Step 6)

- `aidlc-docs/construction/u5-traffic/functional-design/business-logic-model.md`
- `aidlc-docs/construction/u5-traffic/functional-design/business-rules.md`
- `aidlc-docs/construction/u5-traffic/functional-design/domain-entities.md`
