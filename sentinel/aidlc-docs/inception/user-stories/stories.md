# User Stories — Sentinel

**Fase**: INCEPTION — User Stories
**Fecha**: 2026-11-07
**Entradas**: `entradas/prd.md` (v3.0), `entradas/pvb.md`, `aidlc-docs/inception/requirements/requirements.md` (aprobado), `aidlc-docs/inception/user-stories/personas.md`
**Scope Lock**: Producto determinista. Ninguna historia incluye agente, LLM, Tool Layer, orquestación IA ni confirmación humana de operaciones. Toda lógica deriva de mediciones y reglas versionadas.

---

## Convenciones

- **ID de historia**: `ST-<módulo>-<n>` en inglés; cuerpo en español.
- **Formato INVEST**: toda historia es independiente, negociable, valiosa, estimable, pequeña y testeable.
- **Criterios de aceptación**: `Given/When/Then` + línea `Verification:` con comando o comprobación medible.
- **Comandos**: son objetivos (target), ejecutables una vez implementado el producto. No se escribe código en esta etapa.
- **Prioridad MoSCoW**: alineada con PRD §8.
- **Personas**: `PER-OPR` (Network Operator), `PER-ADM` (Platform Administrator), `PER-SEC` (Security Reviewer).

---

# PARTE 1 — Functional Stories

## M1 — Configuration & Scope

### ST-M1-01 — Helm-configurable scope and scheduling
**Persona**: PER-ADM / PER-OPR
**Priority**: Must
**Traces**: FR-DISC-03, NFR-OPS-01; PRD §3.3, §9 M1
**Story**: Como Platform Administrator, quiero definir rangos autorizados, puertos, ventanas de agregación, intervalos e umbrales en `values.yaml`, para desplegar Sentinel de forma declarativa y reproducible.

**Acceptance Criteria**
- **Given** un `values.yaml` con rangos, puertos, intervalo de descubrimiento y ventanas, **When** se ejecuta `helm template`, **Then** los manifiestos generados contienen esos valores y no contienen defaults ocultos.
  - **Verification**: `helm template sentinel ./deploy/helm/sentinel --set discovery.interval=15m | grep -c "15m"` devuelve un valor mayor que 0.
- **Given** un `values.yaml` sin un parámetro obligatorio, **When** se ejecuta `helm lint`, **Then** el chart falla con un mensaje que identifica el parámetro faltante.
  - **Verification**: `helm lint ./deploy/helm/sentinel --set discovery.interval=null` retorna exit code distinto de 0.

---

### ST-M1-02 — Authorized scope validation before scanning
**Persona**: PER-SEC / PER-OPR
**Priority**: Must
**Traces**: FR-DISC-01, FR-DISC-02; PRD §3.1, §6.2
**Story**: Como Security Reviewer, quiero que Sentinel rechace cualquier sondeo fuera del alcance autorizado, para garantizar que solo se observen rangos, puertos y métodos aprobados.

**Acceptance Criteria**
- **Given** un rango/puerto no incluido en la allowlist, **When** se inicia un ciclo de descubrimiento, **Then** el Job termina sin enviar paquetes a ese destino y registra `DiscoveryCycleFailed` con la causa.
  - **Verification**: `pytest tests/integration/test_scope_validation.py -k out_of_scope` pasa y el log contiene `scope_violation`.
- **Given** una configuración con `-O`, NSE o UDP solicitados, **When** se valida la configuración, **Then** el sistema rechaza esos métodos.
  - **Verification**: `pytest tests/unit/test_config_validation.py -k forbidden_scan_methods` pasa.

---

### ST-M1-03 — Reserved sensor_id for future multi-sensor
**Persona**: PER-ADM
**Priority**: Could
**Traces**: FR-DISC-04; PRD §8 Could Have
**Story**: Como Platform Administrator, quiero que toda observación incluya un `sensor_id`, para habilitar en el futuro múltiples sensores sin cambiar el modelo de datos.

**Acceptance Criteria**
- **Given** un sensor configurado con `sensor.id=sensor-01`, **When** se ingiere una observación, **Then** la respuesta y el registro persistido contienen `sensor_id=sensor-01`.
  - **Verification**: `curl -s localhost:8080/api/v1/assets | jq -e '.items[0].sensor_id == "sensor-01"'` retorna 0.

---

### ST-M1-04 — Optional read-only SNMP discovery module
**Persona**: PER-OPR / PER-ADM
**Priority**: Should
**Traces**: FR-DISC-05; PRD §8 Should Have
**Story**: Como Network Operator, quiero habilitar opcionalmente descubrimiento SNMP de solo lectura con OIDs configurables, para enriquecer el inventario de dispositivos de red cuando el entorno lo permita.

**Acceptance Criteria**
- **Given** `snmp.enabled=false`, **When** se despliega el chart, **Then** no se ejecuta ningún sondeo SNMP.
  - **Verification**: `helm template sentinel ./deploy/helm/sentinel --set snmp.enabled=false | grep -c "snmp"` retorna 0 en los workloads.
- **Given** `snmp.enabled=true` con OIDs configurables y credenciales v2c/v3, **When** se ejecuta un ciclo, **Then** las observaciones SNMP se envían al Core con método `snmp` y certeza declarada.
  - **Verification**: `pytest tests/integration/test_snmp_discovery.py -k read_only` pasa.

---

## M2 — Discovery

### ST-M2-01 — Periodic ARP/ICMP/TCP discovery
**Persona**: PER-OPR / PER-ADM
**Priority**: Must
**Traces**: FR-DISC-01, FR-DISC-03; PRD §3.1, UC-01, §9 M2
**Story**: Como Network Operator, quiero que Sentinel ejecute descubrimiento periódico con ARP, ICMP echo y TCP connect sobre los rangos autorizados, para mantener actualizado el catálogo de activos visibles.

**Acceptance Criteria**
- **Given** un intervalo configurado de 15 minutos y un rango autorizado, **When** pasa el intervalo, **Then** se ejecuta un CronJob/Job de descubrimiento y sus observaciones llegan al Core.
  - **Verification**: `kubectl get jobs -n sentinel -o jsonpath='{.items[*].metadata.name}' | grep -c discovery` devuelve un valor mayor que 0.
- **Given** dos ciclos consecutivos exitosos, **When** se consulta el inventario, **Then** los activos del ground truth aparecen con `observed_at` actualizado.
  - **Verification**: `curl -s localhost:8080/api/v1/assets | jq -e '.items | length > 0'` retorna 0.

---

### ST-M2-02 — Light service and version probing
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-DISC-02; PRD §3.1, §9 M2
**Story**: Como Network Operator, quiero que Sentinel ejecute Nmap `-sV --version-light` solo sobre puertos TCP autorizados, para conocer servicios y versiones sin usar modos agresivos.

**Acceptance Criteria**
- **Given** un puerto TCP autorizado abierto, **When** finaliza el ciclo, **Then** el inventario registra el puerto con estado `open`, transporte `tcp` y servicio con nombre o `desconocido`.
  - **Verification**: `curl -s localhost:8080/api/v1/assets | jq -e '[.items[].ports[] | select(.state=="open" and .transport=="tcp")] | length > 0'` retorna 0.
- **Given** la configuración del escáner, **When** se inspeccionan los argumentos, **Then** no aparecen `-O`, scripts NSE, UDP ni modo agresivo.
  - **Verification**: `pytest tests/unit/test_nmap_args.py -k no_aggressive_flags` pasa.

---

### ST-M2-03 — Asset first seen event
**Persona**: PER-OPR
**Priority**: Must
**Traces**: E-01, FR-CORE-05; PRD §3.4, UC-02, GT-02
**Story**: Como Network Operator, quiero que un activo visible que no existía en un ciclo exitoso anterior se registre como `AssetFirstSeen`, para identificar nuevas apariciones en la red.

**Acceptance Criteria**
- **Given** un inventario sin el host `192.0.2.50`, **When** un ciclo exitoso observa `192.0.2.50`, **Then** se crea el activo y se registra el evento `AssetFirstSeen` sin generar alerta.
  - **Verification**: `pytest tests/integration/test_gt02_new_host.py` pasa y el log contiene `"event":"AssetFirstSeen"`.
- **Given** el mismo host en el siguiente ciclo, **When** se reconcilia, **Then** no se duplica el activo ni se repite `AssetFirstSeen`.
  - **Verification**: `curl -s localhost:8080/api/v1/assets | jq -e '[.items[] | select(.ip=="192.0.2.50")] | length == 1'` retorna 0.

---

### ST-M2-04 — Asset missing after N successful cycles
**Persona**: PER-OPR / PER-SEC
**Priority**: Must
**Traces**: E-02; PRD §3.4, UC-02, GT-03
**Story**: Como Network Operator, quiero que un activo esperado se marque como ausente solo tras N ciclos de descubrimiento exitosos, para evitar falsos ausentes por ciclos fallidos o parciales.

**Acceptance Criteria**
- **Given** un activo esperado y N=2 ciclos exitosos consecutivos sin observarlo, **When** se reconcilia el inventario, **Then** el activo queda en estado `missing` y se registra `AssetMissing` sin alerta.
  - **Verification**: `pytest tests/integration/test_gt03_host_absent.py` pasa y el estado del activo es `missing`.
- **Given** un ciclo fallido o con cobertura parcial, **When** el activo no aparece, **Then** no se marca `missing` ni se registra `AssetMissing`.
  - **Verification**: `pytest tests/integration/test_gt03_host_absent.py -k partial_cycle` pasa.

---

### ST-M2-05 — Port or service change event
**Persona**: PER-OPR
**Priority**: Should
**Traces**: E-03; PRD §3.4, UC-02
**Story**: Como Network Operator, quiero que los cambios de puertos/servicios observados se registren como `PortServiceChanged`, para conservar historial de cambios sin generar alertas por defecto.

**Acceptance Criteria**
- **Given** un activo con puerto 22 abierto y luego cerrado en un ciclo posterior, **When** se reconcilia, **Then** se registra `PortServiceChanged` con el estado anterior y el nuevo.
  - **Verification**: `pytest tests/integration/test_port_service_change.py` pasa y el log contiene `"event":"PortServiceChanged"`.
- **Given** un cambio de puerto/servicio, **When** se revisan las alertas, **Then** no se genera ninguna alerta por defecto.
  - **Verification**: `curl -s localhost:9093/api/v2/alerts | jq -e '[.[] | select(.labels.event=="PortServiceChanged")] | length == 0'` retorna 0.

---

### ST-M2-06 — Discovery cycle failure handling
**Persona**: PER-ADM / PER-SEC
**Priority**: Must
**Traces**: E-07; PRD §3.4, §7.3
**Story**: Como Platform Administrator, quiero que un Job de descubrimiento fallido o parcial registre `DiscoveryCycleFailed` y actualice las métricas del ciclo, para distinguir un fallo operativo de una red sin activos.

**Acceptance Criteria**
- **Given** un Job de descubrimiento que falla, **When** finaliza, **Then** se registra `DiscoveryCycleFailed` con la causa y no se emite `AssetMissing`.
  - **Verification**: `pytest tests/integration/test_discovery_failure.py` pasa y el log contiene `"event":"DiscoveryCycleFailed"`.
- **Given** un fallo de descubrimiento, **When** se consulta `/metrics`, **Then** el contador de ciclos fallidos aumentó.
  - **Verification**: `curl -s localhost:9108/metrics | grep -E '^sentinel_discovery_cycles_failed_total [1-9]'` devuelve una línea.

---

## M3 — Traffic Sensor

### ST-M3-01 — Minimal traffic metadata capture on SPAN
**Persona**: PER-OPR / PER-ADM
**Priority**: Must
**Traces**: FR-TRAF-01, FR-TRAF-02, FR-TRAF-03; PRD §3.2, §9 M3
**Story**: Como Network Operator, quiero capturar metadatos mínimos de tráfico IP desde un puerto mirror/SPAN con `hostNetwork`, para medir bytes y flujos sin almacenar payload.

**Acceptance Criteria**
- **Given** un sensor con `hostNetwork: true` y capabilities justificadas, **When** recibe tráfico en la interfaz configurada, **Then** extrae solo `observed_at`, `protocol`, `src_ip`, `dst_ip`, `packet_length_bytes`, `interface` y `sensor_id`.
  - **Verification**: `pytest tests/unit/test_flow_normalization.py -k minimal_fields` pasa.
- **Given** un paquete capturado, **When** se persiste el evento, **Then** el registro no contiene payload ni MAC/puerto para tráfico IP.
  - **Verification**: `pytest tests/security/test_no_payload_stored.py` pasa.

---

### ST-M3-02 — Configurable aggregation windows
**Persona**: PER-ADM / PER-OPR
**Priority**: Must
**Traces**: FR-TRAF-04; PRD §3.3
**Story**: Como Platform Administrator, quiero configurar la ventana de agregación entre 1s, 5s, 10s, 30s y 60s, para ajustar la resolución temporal al laboratorio.

**Acceptance Criteria**
- **Given** `traffic.window=5s`, **When** se procesan paquetes durante 25s, **Then** se generan cinco ventanas con `bytes_per_second` sobre la duración efectiva.
  - **Verification**: `pytest tests/unit/test_aggregation.py -k five_second_windows` pasa.
- **Given** una ventana no soportada, **When** se valida la configuración, **Then** el despliegue se rechaza.
  - **Verification**: `helm lint ./deploy/helm/sentinel --set traffic.window=7s` retorna exit code distinto de 0.

---

### ST-M3-03 — Export aggregated flows to Core
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-TRAF-05, FR-CORE-01; PRD §3.2, §9 M4
**Story**: Como Network Operator, quiero que el sensor envíe los agregados al Core vía HTTP/JSON, para centralizar la persistencia y consulta de telemetría.

**Acceptance Criteria**
- **Given** una ventana agregada, **When** el sensor la envía al Core, **Then** el Core responde 2xx y la ventana queda consultable.
  - **Verification**: `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8080/api/v1/ingest/traffic -d @fixtures/window.json` devuelve `202`.
- **Given** un fallo temporal del Core, **When** el sensor reintenta, **Then** no se generan duplicados por la identidad estable del evento.
  - **Verification**: `pytest tests/integration/test_ingest_idempotency.py` pasa.

---

### ST-M3-04 — ARP observation and IP-MAC tracking
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-ARP-01, FR-ARP-02; PRD §3.2, UC-05
**Story**: Como Network Operator, quiero observar ARP request y reply y mantener las asociaciones IP-MAC por interfaz, para detectar cambios de asociación en capa 2.

**Acceptance Criteria**
- **Given** tráfico ARP con opcode 1 y 2, **When** el sensor lo procesa, **Then** registra `op`, `psrc`, `pdst`, `hwsrc`, `hwdst`, hora, interfaz y sensor.
  - **Verification**: `pytest tests/unit/test_arp_parsing.py -k request_and_reply` pasa.
- **Given** una asociación IP-MAC observada, **When** llega otro ARP con distinto MAC para la misma IP, **Then** se registra el cambio de asociación.
  - **Verification**: `pytest tests/integration/test_arp_mapping_change.py` pasa.

---

### ST-M3-05 — ARP rate per interface
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-ARP-03; PRD §3.2, R-02
**Story**: Como Network Operator, quiero que el sensor calcule mensajes ARP por segundo por interfaz, para exponer la condición `ArpRateThresholdExceeded`.

**Acceptance Criteria**
- **Given** 100 mensajes ARP en 10s en una interfaz, **When** se agrega la ventana, **Then** `arp_messages_per_second` es 10.
  - **Verification**: `pytest tests/unit/test_arp_rate.py -k ten_per_second` pasa.
- **Given** una tasa ARP superior al umbral configurado, **When** el Core publica el indicador, **Then** Prometheus evalúa la regla R-02.
  - **Verification**: `curl -s localhost:9108/metrics | grep -E '^sentinel_arp_rate_exceeded'` devuelve una línea.

---

### ST-M3-06 — ARP mapping changed alert
**Persona**: PER-OPR / PER-SEC
**Priority**: Must
**Traces**: FR-ARP-04, E-04; PRD §3.2, R-03, UC-05
**Story**: Como Network Operator, quiero recibir una alerta `ArpMappingChanged` cuando cambia una asociación IP-MAC, para revisar el cambio sin que el sistema afirme que hubo spoofing.

**Acceptance Criteria**
- **Given** una asociación previa IP-MAC y una nueva distinta, **When** se procesa el ARP, **Then** se registra el evento y se dispara la alerta R-03.
  - **Verification**: `pytest tests/integration/test_arp_mapping_change.py -k alert` pasa.
- **Given** la alerta disparada, **When** se consulta su contenido, **Then** no atribuye ataque ni usa `spoofing` como diagnóstico.
  - **Verification**: `curl -s localhost:9093/api/v2/alerts | jq -r '.[] | select(.labels.alertname=="ArpMappingChanged") | .annotations' | grep -c -i "spoofing"` retorna 0.

---

## M4 — Core API, Persistence & Export

### ST-M4-01 — Ingestion API for sensor observations
**Persona**: PER-OPR / PER-ADM
**Priority**: Must
**Traces**: FR-CORE-01, FR-TRAF-05; PRD §9 M4
**Story**: Como Network Operator, quiero una API HTTP/JSON de ingesta para que el sensor envíe observaciones de descubrimiento, tráfico y ARP al Core, para unificar su procesamiento.

**Acceptance Criteria**
- **Given** un lote válido, **When** se envía por `POST /api/v1/ingest`, **Then** el Core responde 2xx y persiste los registros.
  - **Verification**: `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8080/api/v1/ingest -H 'Content-Type: application/json' -d @fixtures/observations.json` devuelve `202`.
- **Given** un lote con un campo obligatorio faltante, **When** se envía, **Then** el Core responde 400 con el campo inválido.
  - **Verification**: `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8080/api/v1/ingest -d '{}'` devuelve `400`.

---

### ST-M4-02 — SQLite persistence on PVC with restart recovery
**Persona**: PER-ADM / PER-OPR
**Priority**: Must
**Traces**: FR-CORE-03, NFR-AVAIL-02; PRD §9 M4
**Story**: Como Platform Administrator, quiero que el Core persista eventos, activos, alertas y baselines en SQLite sobre un PVC y recupere el estado tras reinicios, para no perder evidencia.

**Acceptance Criteria**
- **Given** un PVC montado en el Core, **When** se ingiere un evento y el Pod se reinicia, **Then** el evento sigue consultable tras el reinicio.
  - **Verification**: `pytest tests/integration/test_persistence_restart.py` pasa.
- **Given** un despliegue sin PVC, **When** se ejecuta `helm template`, **Then** el chart rechaza la configuración.
  - **Verification**: `helm template sentinel ./deploy/helm/sentinel --set persistence.enabled=false` retorna exit code distinto de 0.

---

### ST-M4-03 — Stable event identity and deduplication
**Persona**: PER-ADM / PER-SEC
**Priority**: Must
**Traces**: FR-CORE-04; PRD §3.5, U5
**Story**: Como Security Reviewer, quiero que cada evento persistido tenga un UUID estable y que los lotes repetidos no dupliquen hechos, para garantizar idempotencia y evidencia consistente.

**Acceptance Criteria**
- **Given** el mismo lote enviado dos veces, **When** el Core lo procesa, **Then** el número de eventos persistidos no cambia en la segunda ingesta.
  - **Verification**: `pytest tests/integration/test_ingest_idempotency.py -k uuid_dedup` pasa.
- **Given** un evento persistido, **When** se consulta, **Then** incluye un `event_id` UUID válido.
  - **Verification**: `curl -s localhost:8080/api/v1/events | jq -e '.items[0].event_id | test("^[0-9a-f-]{36}$")'` retorna 0.

---

### ST-M4-04 — Normalize and correlate observations
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-CORE-05; PRD §9 M4
**Story**: Como Network Operator, quiero que el Core normalice y correlacione descubrimiento, tráfico y ARP, para presentar una vista coherente por activo y ventana temporal.

**Acceptance Criteria**
- **Given** una observación de descubrimiento y otra de tráfico del mismo host, **When** se consulta el activo, **Then** ambas fuentes aparecen correlacionadas por IP y ventana.
  - **Verification**: `pytest tests/unit/test_correlation.py -k discovery_and_traffic` pasa.
- **Given** observaciones con distinto formato de MAC, **When** se normalizan, **Then** se almacenan en un formato canónico único.
  - **Verification**: `pytest tests/unit/test_normalization.py -k mac_canonical` pasa.

---

### ST-M4-05 — Structured JSON Lines event logs
**Persona**: PER-OPR / PER-SEC
**Priority**: Must
**Traces**: FR-EXP-01; PRD §3.5
**Story**: Como Network Operator, quiero que los eventos se emitan como JSON Lines con hora, activo/par, método, protocolo, condición, regla, umbral, valor medido y resultado, para revisar evidencia legible por máquina.

**Acceptance Criteria**
- **Given** un evento persistido, **When** se lee el log, **Then** cada línea es JSON válido y contiene los campos de evidencia requeridos.
  - **Verification**: `pytest tests/integration/test_structured_logs.py -k jsonl_fields` pasa.
- **Given** un evento y una alerta, **When** se inspecciona el log, **Then** el tipo distingue observación, inferencia, evento y alerta.
  - **Verification**: `pytest tests/integration/test_structured_logs.py -k source_kind` pasa.

---

### ST-M4-06 — On-demand CSV bulk export
**Persona**: PER-OPR / PER-SEC
**Priority**: Must
**Traces**: FR-EXP-02, FR-EXP-03; PRD §3.5, U5
**Story**: Como Network Operator, quiero exportar bajo demanda todos los eventos en CSV con campos completos, para analizarlos fuera de Sentinel.

**Acceptance Criteria**
- **Given** eventos persistidos, **When** se solicita `GET /api/v1/export?format=csv`, **Then** la respuesta es CSV con cabeceras `timestamp, asset_or_pair, method, protocol, condition, rule, threshold, measured_value, result`.
  - **Verification**: `curl -s 'localhost:8080/api/v1/export?format=csv' | head -1 | grep -c 'timestamp,asset_or_pair,method,protocol,condition,rule,threshold,measured_value,result'` retorna 1.
- **Given** una exportación solicitada, **When** se completa, **Then** no se programa envío periódico ni push.
  - **Verification**: `pytest tests/integration/test_export_on_demand.py -k no_scheduler` pasa.

---

### ST-M4-07 — Query API for assets, events and alerts
**Persona**: PER-OPR
**Priority**: Should
**Traces**: FR-CORE-01; PRD §7.1, §9 M4
**Story**: Como Network Operator, quiero consultar activos, eventos y alertas por API con filtros, para obtener detalles que no se muestran en dashboards.

**Acceptance Criteria**
- **Given** activos persistidos, **When** se consulta `GET /api/v1/assets?status=missing`, **Then** solo se devuelven activos en ese estado.
  - **Verification**: `curl -s 'localhost:8080/api/v1/assets?status=missing' | jq -e '[.items[] | select(.status!="missing")] | length == 0'` retorna 0.
- **Given** un rango temporal, **When** se consultan eventos, **Then** solo se devuelven eventos dentro del rango.
  - **Verification**: `pytest tests/integration/test_query_filters.py -k time_range` pasa.

---

## M5 — Deterministic Conditions & Baselines

### ST-M5-01 — Baseline from first five samples
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-BASE-01, FR-BASE-02; PRD §3.3
**Story**: Como Network Operator, quiero que el Core calcule la línea base con las primeras cinco muestras (media y varianza muestral) por métrica de flujo, para disponer de una referencia estadística reproducible.

**Acceptance Criteria**
- **Given** cinco muestras consecutivas de bytes, **When** se calcula la baseline, **Then** la media es la media aritmética y la varianza usa denominador `n-1=4`.
  - **Verification**: `pytest tests/unit/test_baseline.py -k five_samples` pasa.
- **Given** menos de cinco muestras, **When** se consulta el estado de la baseline, **Then** figura como `establishing` y no `available`.
  - **Verification**: `curl -s localhost:9108/metrics | grep 'sentinel_baseline_status' | grep -c 'establishing'` devuelve un valor mayor que 0.

---

### ST-M5-02 — Configurable threshold with absolute fallback
**Persona**: PER-ADM / PER-OPR
**Priority**: Must
**Traces**: FR-BASE-03; PRD §3.3
**Story**: Como Platform Administrator, quiero configurar `k` para el umbral `mu + k·s` y disponer de un umbral absoluto de respaldo, para adaptar la sensibilidad sin cambiar código.

**Acceptance Criteria**
- **Given** `baseline.k=3`, **When** se evalúa una medición, **Then** la condición es verdadera solo si supera `mu + 3·s`.
  - **Verification**: `pytest tests/unit/test_threshold.py -k mu_plus_k_sigma` pasa.
- **Given** una baseline no disponible, **When** se evalúa la medición, **Then** se usa el umbral absoluto configurado.
  - **Verification**: `pytest tests/unit/test_threshold.py -k absolute_fallback` pasa.

---

### ST-M5-03 — Suppress alerts during baseline establishment
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-BASE-04; PRD §3.3
**Story**: Como Network Operator, quiero que no se disparen alertas basadas en baseline durante la ventana de inicialización, para evitar ruido por muestras insuficientes.

**Acceptance Criteria**
- **Given** la ventana de inicialización activa, **When** una medición supera el umbral provisional, **Then** no se dispara `TrafficThresholdExceeded`.
  - **Verification**: `pytest tests/integration/test_baseline_suppression.py -k init_window` pasa.
- **Given** la baseline queda `available`, **When** una medición supera `mu + k·s`, **Then** la condición se publica normalmente.
  - **Verification**: `pytest tests/integration/test_baseline_suppression.py -k after_window` pasa.

---

### ST-M5-04 — Publish deterministic condition indicators
**Persona**: PER-OPR / PER-ADM
**Priority**: Must
**Traces**: FR-BASE-05, FR-OBS-02; PRD §3.3, §3.4
**Story**: Como Network Operator, quiero que el Core publique indicadores deterministas de condición de tráfico, ARP y disponibilidad del sensor, para que Prometheus evalúe las reglas de alerta.

**Acceptance Criteria**
- **Given** una condición de tráfico verdadera, **When** se consulta `/metrics`, **Then** `sentinel_traffic_threshold_exceeded` vale 1 para la interfaz/protocolo evaluado.
  - **Verification**: `curl -s localhost:9108/metrics | grep -E '^sentinel_traffic_threshold_exceeded 1'` devuelve una línea.
- **Given** el sensor sin latidos dentro del plazo, **When** se consulta `/metrics`, **Then** `sentinel_collector_up{collector="traffic"}` vale 0.
  - **Verification**: `curl -s localhost:9108/metrics | grep -E '^sentinel_collector_up\{collector="traffic"\} 0'` devuelve una línea.

---

## M6 — Metrics Exposure

### ST-M6-01 — Prometheus-compatible /metrics on port 9108
**Persona**: PER-ADM / PER-OPR
**Priority**: Must
**Traces**: FR-CORE-02; PRD §9 M6
**Story**: Como Platform Administrator, quiero que el Core exponga `/metrics` en el puerto 9108, para que Prometheus recoja indicadores sin adaptadores adicionales.

**Acceptance Criteria**
- **Given** el Core en ejecución, **When** se consulta `GET :9108/metrics`, **Then** responde 200 con formato Prometheus.
  - **Verification**: `curl -s -o /dev/null -w '%{http_code}' localhost:9108/metrics` devuelve `200`.
- **Given** el Service del Core, **When** se inspecciona, **Then** el puerto se llama `metrics` y apunta a 9108.
  - **Verification**: `kubectl get svc sentinel-core -n sentinel -o jsonpath='{.spec.ports[?(@.name=="metrics")].port}'` devuelve `9108`.

---

### ST-M6-02 — Aggregated metrics without high-cardinality labels
**Persona**: PER-OPR / PER-SEC
**Priority**: Must
**Traces**: FR-OBS-02; PRD §3.2, §9 M6
**Story**: Como Network Operator, quiero métricas agregadas de inventario, flujos, alertas, baseline y salud del sensor sin etiquetas `src_ip`/`dst_ip`, para evitar cardinalidad alta y proteger datos.

**Acceptance Criteria**
- **Given** tráfico agregado, **When** se consulta `/metrics`, **Then** las métricas no usan `src_ip` ni `dst_ip` como labels.
  - **Verification**: `curl -s localhost:9108/metrics | grep -E 'src_ip|dst_ip' | grep -c ''` retorna 0.
- **Given** la salud del sensor, **When** se consulta `/metrics`, **Then** existe `sentinel_collector_up` agregado por `collector`.
  - **Verification**: `curl -s localhost:9108/metrics | grep -E '^sentinel_collector_up\{collector='` devuelve una línea.

---

### ST-M6-03 — ServiceMonitor for metrics scraping
**Persona**: PER-ADM
**Priority**: Should
**Traces**: FR-OBS-02, FR-OBS-01; PRD §9 M6
**Story**: Como Platform Administrator, quiero un ServiceMonitor que seleccione el Service `sentinel-core`, para que Prometheus descubra el endpoint de métricas automáticamente.

**Acceptance Criteria**
- **Given** `kube-prometheus-stack` instalado, **When** se aplica el chart, **Then** el ServiceMonitor selecciona `app.kubernetes.io/name=sentinel-core`.
  - **Verification**: `kubectl get servicemonitor sentinel-core -n sentinel -o jsonpath='{.spec.selector.matchLabels.app\\.kubernetes\\.io/name}'` devuelve `sentinel-core`.
- **Given** el ServiceMonitor activo, **When** se consultan los targets de Prometheus, **Then** el target de Sentinel aparece `up`.
  - **Verification**: `curl -s localhost:9090/api/v1/targets | jq -e '[.data.activeTargets[] | select(.labels.job=="sentinel-core") | select(.health=="up")] | length > 0'` retorna 0.

---

## M7 — Observability & Alerting

### ST-M7-01 — Traffic threshold PrometheusRule
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-BASE-05, R-01; PRD §3.4, GT-04
**Story**: Como Network Operator, quiero una `PrometheusRule` que aplique la duración configurada a `TrafficThresholdExceeded`, para recibir alertas de tráfico alto sin atribución de ataque.

**Acceptance Criteria**
- **Given** la condición de tráfico verdadera durante la duración `for`, **When** Prometheus evalúa la regla, **Then** la alerta `TrafficThresholdExceeded` queda activa.
  - **Verification**: `pytest tests/integration/test_gt04_high_traffic.py` pasa y Alertmanager muestra la alerta.
- **Given** la alerta activa, **When** se consulta su anotación, **Then** indica umbral excedido y no afirma DDoS ni ataque.
  - **Verification**: `curl -s localhost:9093/api/v2/alerts | jq -r '.[] | select(.labels.alertname=="TrafficThresholdExceeded") | .annotations' | grep -c -iE "ddos|ataque confirmado"` retorna 0.

---

### ST-M7-02 — ARP rate PrometheusRule
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-ARP-03, R-02; PRD §3.4
**Story**: Como Network Operator, quiero una `PrometheusRule` para `ArpRateThresholdExceeded` con duración configurable, para alertar actividad ARP por encima del umbral.

**Acceptance Criteria**
- **Given** `sentinel_arp_rate_exceeded=1` durante la duración `for`, **When** Prometheus evalúa, **Then** la alerta `ArpRateThresholdExceeded` se activa.
  - **Verification**: `curl -s localhost:9093/api/v2/alerts | jq -e '[.[] | select(.labels.alertname=="ArpRateThresholdExceeded")] | length > 0'` retorna 0.
- **Given** la alerta activa, **When** se consulta, **Then** no afirma flooding malicioso confirmado.
  - **Verification**: `curl -s localhost:9093/api/v2/alerts | jq -r '.[] | select(.labels.alertname=="ArpRateThresholdExceeded") | .annotations' | grep -c -i "flooding malicioso"` retorna 0.

---

### ST-M7-03 — ArpMappingChanged rule
**Persona**: PER-OPR / PER-SEC
**Priority**: Must
**Traces**: FR-ARP-04, R-03; PRD §3.4
**Story**: Como Network Operator, quiero una regla `ArpMappingChanged` que se dispare cuando cambie la asociación IP-MAC, para revisar el cambio observado.

**Acceptance Criteria**
- **Given** un cambio de asociación IP-MAC, **When** se evalúa la regla, **Then** la alerta `ArpMappingChanged` queda activa con la IP y las MAC observadas.
  - **Verification**: `pytest tests/integration/test_arp_mapping_change.py -k rule` pasa.
- **Given** la alerta, **When** se revisa, **Then** no contiene la palabra `spoofing` como diagnóstico.
  - **Verification**: `curl -s localhost:9093/api/v2/alerts | jq -r '.[] | select(.labels.alertname=="ArpMappingChanged") | .annotations' | grep -c -i "spoofing"` retorna 0.

---

### ST-M7-04 — SensorUnavailable alert
**Persona**: PER-OPR / PER-ADM
**Priority**: Must
**Traces**: FR-BASE-05, R-04, NFR-AVAIL-01; PRD §3.4, §7.3, GT-05
**Story**: Como Network Operator, quiero recibir `SensorUnavailable` cuando el Traffic Sensor deje de enviar latidos/ventanas dentro del plazo configurado, para detectar el hueco de visibilidad.

**Acceptance Criteria**
- **Given** el sensor sin telemetría más allá del plazo, **When** Prometheus evalúa `sentinel_collector_up{collector="traffic"}==0`, **Then** la alerta `SensorUnavailable` se activa.
  - **Verification**: `pytest tests/integration/test_gt05_sensor_down.py` pasa y la alerta aparece en Alertmanager.
- **Given** la recuperación del sensor, **When** vuelve a enviar telemetría, **Then** la alerta se resuelve y el hueco queda documentado en evidencia.
  - **Verification**: `curl -s localhost:9093/api/v2/alerts | jq -e '[.[] | select(.labels.alertname=="SensorUnavailable")] | length == 0'` retorna 0 tras recuperación.

---

### ST-M7-05 — Grafana dashboards and observability stack
**Persona**: PER-OPR / PER-ADM
**Priority**: Must
**Traces**: FR-OBS-01, FR-OBS-04; PRD §7.1, §9 M7
**Story**: Como Network Operator, quiero dashboards de inventario, baseline de tráfico, timeline de alertas y salud del sensor, para revisar el estado sin consultar la API manualmente.

**Acceptance Criteria**
- **Given** `kube-prometheus-stack` desplegado, **When** se importan los dashboards de Sentinel, **Then** Grafana muestra los paneles de inventario, tráfico, alertas y salud del sensor.
  - **Verification**: `curl -s -u admin:admin localhost:3000/api/search?query=Sentinel | jq -e 'length >= 4'` retorna 0.
- **Given** un cambio de inventario, **When** se refresca el dashboard, **Then** el panel refleja el nuevo conteo dentro del intervalo de refresco.
  - **Verification**: `pytest tests/integration/test_grafana_dashboards.py -k inventory_panel` pasa.

---

### ST-M7-06 — Alertmanager webhook receiver
**Persona**: PER-ADM / PER-OPR
**Priority**: Should
**Traces**: FR-OBS-03; PRD §8 Should Have
**Story**: Como Platform Administrator, quiero configurar Alertmanager con un receiver webhook, para demostrar el enrutamiento externo de notificaciones sin canales adicionales.

**Acceptance Criteria**
- **Given** un receiver webhook configurado, **When** una alerta se activa, **Then** Alertmanager envía la notificación al endpoint configurado.
  - **Verification**: `pytest tests/integration/test_alertmanager_webhook.py` pasa contra un receptor local de prueba.
- **Given** la documentación de operación, **When** se revisa, **Then** describe el uso de `webhook.site` o receptor equivalente para demos.
  - **Verification**: `grep -c "webhook" docs/operations.md` devuelve un valor mayor que 0.

---

## M8 — Kubernetes Runtime

### ST-M8-01 — Deploy Sentinel via Helm chart
**Persona**: PER-ADM
**Priority**: Must
**Traces**: FR-OBS-01, NFR-TECH-01; PRD §8, §9 M8
**Story**: Como Platform Administrator, quiero desplegar Sentinel con un Helm chart versionado, para instalar y actualizar el producto de forma reproducible en Kubernetes 1.28+.

**Acceptance Criteria**
- **Given** un clúster compatible, **When** se ejecuta `helm install sentinel`, **Then** se crean los recursos del chart en el namespace y `helm status` reporta `deployed`.
  - **Verification**: `helm install sentinel ./deploy/helm/sentinel -n sentinel --create-namespace && helm status sentinel -n sentinel -o json | jq -r '.info.status'` devuelve `deployed`.
- **Given** el chart, **When** se ejecuta `helm lint` y `helm template`, **Then** ambas validaciones terminan sin error.
  - **Verification**: `helm lint ./deploy/helm/sentinel && helm template sentinel ./deploy/helm/sentinel >/dev/null` retorna 0.

---

### ST-M8-02 — Declarative workloads, services and PVC
**Persona**: PER-ADM
**Priority**: Must
**Traces**: NFR-TECH-01, FR-CORE-03; PRD §9 M8
**Story**: Como Platform Administrator, quiero que el chart declare CronJobs/Jobs de descubrimiento, Deployments de Core/Sensor, Services, ConfigMaps, Secrets y PVC, para operar Sentinel con manifiestos declarativos.

**Acceptance Criteria**
- **Given** el chart desplegado, **When** se listan los workloads, **Then** existen el CronJob de descubrimiento, el Deployment del Core y el Deployment del Sensor.
  - **Verification**: `kubectl get deploy,cronjob -n sentinel -o name | grep -c -E 'deploy.apps/sentinel-core|deploy.apps/sentinel-sensor|cronjob.batch/sentinel-discovery'` devuelve 3.
- **Given** el Core, **When** se inspecciona, **Then** monta un PVC para SQLite.
  - **Verification**: `kubectl get deploy sentinel-core -n sentinel -o jsonpath='{.spec.template.spec.volumes[*].persistentVolumeClaim.claimName}'` devuelve un nombre no vacío.

---

### ST-M8-03 — Deploy and verify on kind/k3s
**Persona**: PER-ADM
**Priority**: Must
**Traces**: NFR-TECH-01; PRD §8, §13
**Story**: Como Platform Administrator, quiero desplegar Sentinel en kind o k3s como parte del pipeline, para validar el comportamiento en un clúster reproducible antes de producción.

**Acceptance Criteria**
- **Given** un clúster kind creado en CI, **When** se ejecuta el paso de despliegue, **Then** los Pods de Sentinel alcanzan estado `Running` o `Completed`.
  - **Verification**: `kubectl wait --for=condition=Available deploy/sentinel-core deploy/sentinel-sensor -n sentinel --timeout=300s` retorna 0.
- **Given** el despliegue, **When** se ejecuta `helm test`, **Then** el test del chart pasa.
  - **Verification**: `helm test sentinel -n sentinel` retorna 0.

---

### ST-M8-04 — Single OCI image with separate commands
**Persona**: PER-ADM
**Priority**: Should
**Traces**: NFR-TECH-02; PRD §9 M8
**Story**: Como Platform Administrator, quiero una imagen OCI común con comandos separados para Core, Sensor y Discovery, para reducir variantes de build y superficie de mantenimiento.

**Acceptance Criteria**
- **Given** la imagen construida, **When** se ejecuta con el comando del Core, **Then** arranca el Core; con el comando del Sensor, arranca el Sensor.
  - **Verification**: `docker run --rm sentinel:test sentinel-core --help` y `docker run --rm sentinel:test sentinel-sensor --help` retornan 0.
- **Given** la imagen, **When** se inspecciona, **Then** la base es Alpine y corre como usuario no root (excepto el sensor con capabilities documentadas).
  - **Verification**: `docker image inspect sentinel:test --format '{{.Config.User}}'` devuelve un usuario no vacío y distinto de `root`; el sensor se valida en ST-M9-03.

---

## M9 — Security & Negative Tests

### ST-M9-01 — Least-privilege RBAC
**Persona**: PER-SEC / PER-ADM
**Priority**: Must
**Traces**: FR-SEC-03; PRD §9 M9
**Story**: Como Security Reviewer, quiero ServiceAccounts separadas con permisos mínimos para Core, Sensor y Grafana, para limitar el impacto de un compromiso.

**Acceptance Criteria**
- **Given** los manifiestos RBAC, **When** se auditan los Roles/ClusterRoles, **Then** Sentinel no usa `cluster-admin` y los permisos son de solo lectura sobre los recursos necesarios.
  - **Verification**: `kubectl get rolebinding,clusterrolebinding -o json | jq -e '[.items[] | select(.subjects[]?.name | test("sentinel")) | select(.roleRef.name=="cluster-admin")] | length == 0'` retorna 0.
- **Given** las ServiceAccounts, **When** se listan, **Then** existen cuentas separadas para Core, Sensor y Grafana.
  - **Verification**: `kubectl get sa -n sentinel -o name | grep -c -E 'sentinel-core|sentinel-sensor|sentinel-grafana'` devuelve 3.

---

### ST-M9-02 — Default-deny NetworkPolicy with allow rules
**Persona**: PER-SEC / PER-ADM
**Priority**: Should
**Traces**: FR-SEC-01, FR-SEC-02; PRD §8 Should Have
**Story**: Como Security Reviewer, quiero una NetworkPolicy default-deny que solo permita Core-Sensor, Core-Prometheus y Grafana-Prometheus, para aislar la comunicación interna.

**Acceptance Criteria**
- **Given** las NetworkPolicies aplicadas, **When** se intenta tráfico no permitido entre Pods de Sentinel, **Then** la conexión se bloquea.
  - **Verification**: `pytest tests/integration/test_networkpolicy_deny.py -k default_deny` pasa.
- **Given** la documentación, **When** se revisa, **Then** indica que el CNI debe soportar NetworkPolicy (Calico, Cilium, k3s).
  - **Verification**: `grep -c -E "Calico|Cilium|k3s" docs/deployment.md` devuelve un valor mayor que 0.

---

### ST-M9-03 — Pod Security and justified sensor capabilities
**Persona**: PER-SEC / PER-ADM
**Priority**: Must
**Traces**: FR-SEC-04, FR-TRAF-02, NFR-SEC-02; PRD §6.7, §9 M9
**Story**: Como Security Reviewer, quiero que Core y Grafana usen Pod Security `restricted` y que el Sensor declare únicamente las capabilities necesarias, para reducir privilegios.

**Acceptance Criteria**
- **Given** los namespaces y pods, **When** se inspecciona su configuración de seguridad, **Then** Core y Grafana cumplen `restricted`; el Sensor documenta y limita sus capabilities.
  - **Verification**: `kubectl get ns sentinel -o jsonpath='{.metadata.labels.pod-security\\.kubernetes\\.io/enforce}'` devuelve `restricted`, y `kubectl get pod -n sentinel -l app=sentinel-sensor -o jsonpath='{.items[0].spec.containers[0].securityContext.capabilities}'` lista solo las capabilities justificadas.
- **Given** una capability no justificada añadida al Sensor, **When** se valida el chart, **Then** la validación falla.
  - **Verification**: `pytest tests/unit/test_security_context.py -k unexpected_capability` pasa.

---

### ST-M9-04 — Proof of no writes on endpoints
**Persona**: PER-SEC
**Priority**: Must
**Traces**: NFR-SEC-01; PRD §6.1, §8, §11.2
**Story**: Como Security Reviewer, quiero una prueba negativa que confirme que Sentinel no modifica los activos monitorizados, para validar el principio de solo lectura.

**Acceptance Criteria**
- **Given** un conjunto de activos de laboratorio con estado conocido, **When** Sentinel ejecuta descubrimiento y captura durante un ciclo completo, **Then** no se observa ningún cambio de configuración o estado atribuible a Sentinel.
  - **Verification**: `pytest tests/security/test_no_endpoint_writes.py` pasa y registra la comparación de estado antes/después.
- **Given** los logs de evidencia, **When** se revisan, **Then** no existe ninguna llamada de escritura remota (SNMP set, SSH, API de configuración).
  - **Verification**: `grep -c -E "snmp.*set|ssh|write" evidence/sentinel.log` retorna 0 para operaciones de escritura.

---

## M10 — Operator GUI & Network Report

### ST-M10-01 — Asset inventory view
**Persona**: PER-OPR
**Priority**: Must
**Traces**: FR-GUI-01, FR-GUI-08; NFR-TECH-04
**Story**: Como Network Operator, quiero ver el inventario de activos en una tabla con IP, MAC, hostname, SO, último avistamiento y estado, para revisar la red de un vistazo sin consultar logs.

**Acceptance Criteria**
- **Given** activos persistidos, **When** abro `/ui/assets`, **Then** veo una tabla paginada con las columnas requeridas y cada valor de SO marcado como observado, inferido, declarado o desconocido.
  - **Verification**: `curl -s localhost:8080/ui/assets | grep -c 'data-asset-row'` devuelve un valor mayor que 0 y `pytest tests/integration/test_gui_assets.py -k columns` pasa.
- **Given** un activo con SO desconocido, **When** veo su fila, **Then** muestra `desconocido` y no un valor inventado.
  - **Verification**: `pytest tests/integration/test_gui_assets.py -k unknown_os` pasa.

---

### ST-M10-02 — Asset detail view
**Persona**: PER-OPR / PER-SEC
**Priority**: Must
**Traces**: FR-GUI-02, FR-GUI-08
**Story**: Como Network Operator, quiero abrir el detalle de un activo con su historial de observaciones, eventos, resumen de tráfico y mapeos ARP, para investigar un cambio concreto.

**Acceptance Criteria**
- **Given** un activo persistido, **When** abro `/ui/assets/{id}`, **Then** veo las secciones de observaciones, eventos, tráfico y ARP con datos correlacionados por IP y ventana.
  - **Verification**: `pytest tests/integration/test_gui_asset_detail.py -k sections` pasa.
- **Given** un activo sin observaciones de tráfico, **When** abro su detalle, **Then** la sección de tráfico indica `sin datos` en lugar de ceros inventados.
  - **Verification**: `pytest tests/integration/test_gui_asset_detail.py -k no_traffic` pasa.

---

### ST-M10-03 — Events and alerts timeline
**Persona**: PER-OPR / PER-SEC
**Priority**: Must
**Traces**: FR-GUI-03
**Story**: Como Network Operator, quiero una línea de tiempo de eventos y alertas filtrable por activo, regla y rango temporal, para reconstruir qué ocurrió y cuándo.

**Acceptance Criteria**
- **Given** eventos y alertas persistidos, **When** aplico filtros de activo, regla y rango, **Then** la línea de tiempo muestra solo las coincidencias y distingue `firing` de `resolved`.
  - **Verification**: `pytest tests/integration/test_gui_timeline.py -k filters` pasa.
- **Given** una alerta resuelta, **When** la consulto en la línea de tiempo, **Then** muestra estado `resolved` con su hora de resolución.
  - **Verification**: `pytest tests/integration/test_gui_timeline.py -k resolved_state` pasa.

---

### ST-M10-04 — Trigger discovery for one host or the configured list
**Persona**: PER-OPR / PER-ADM
**Priority**: Should
**Traces**: FR-GUI-04, FR-DISC-06; ST-M1-01
**Story**: Como Network Operator, quiero disparar un ciclo de descubrimiento para un host individual o para la lista explícita configurada, para actualizar el inventario sin esperar al CronJob.

**Acceptance Criteria**
- **Given** `scope.mode=explicit_hosts`, **When** disparo descubrimiento para un host autorizado, **Then** el Core crea el Job correspondiente y la GUI muestra su estado y resultado.
  - **Verification**: `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8080/ui/discovery -d 'host=192.168.1.10'` devuelve `202`.
- **Given** un host fuera de la lista autorizada, **When** intento dispararlo, **Then** el Core responde 400 y registra `scope_violation`.
  - **Verification**: `pytest tests/integration/test_gui_discovery.py -k out_of_scope` pasa.

---

### ST-M10-05 — System health view
**Persona**: PER-OPR / PER-ADM
**Priority**: Must
**Traces**: FR-GUI-05
**Story**: Como Platform Administrator, quiero una vista de salud del sistema con estado del Core, último ciclo exitoso y latido del colector, para distinguir una red sin activos de una falla de telemetría.

**Acceptance Criteria**
- **Given** Core y colectores operativos, **When** abro `/ui/health`, **Then** veo estado, hora del último ciclo exitoso y heartbeat del sensor.
  - **Verification**: `pytest tests/integration/test_gui_health.py -k healthy` pasa.
- **Given** un sensor sin heartbeat, **When** abro la vista de salud, **Then** muestra `sensor caído` y no presenta el inventario vacío como red sin activos.
  - **Verification**: `pytest tests/integration/test_gui_health.py -k sensor_down` pasa.

---

### ST-M10-06 — Network report and export
**Persona**: PER-OPR / PER-SEC
**Priority**: Must
**Traces**: FR-GUI-06, NFR-OPS-05; FR-EXP-02
**Story**: Como Network Operator, quiero generar y descargar un reporte de red en Markdown/PDF y exportar CSV/JSON, para entregar evidencia ordenada de un periodo.

**Acceptance Criteria**
- **Given** un rango de fechas con datos, **When** genero el reporte, **Then** descargo Markdown/PDF con resumen de inventario, cambios, top talkers (si hay tráfico), alertas y rango de evidencia.
  - **Verification**: `curl -s "localhost:8080/ui/report?from=2026-11-01&to=2026-11-07" -o report.md && grep -c '^## ' report.md` devuelve al menos 4.
- **Given** los mismos filtros aplicados dos veces, **When** genero el reporte, **Then** las secciones de resumen son idénticas.
  - **Verification**: `pytest tests/integration/test_report_determinism.py` pasa.
- **Given** el botón de exportación, **When** lo uso, **Then** obtengo CSV/JSON con los campos de evidencia requeridos.
  - **Verification**: `curl -s -o /dev/null -w '%{http_code}' "localhost:8080/api/v1/export?format=csv&from=2026-11-01&to=2026-11-07"` devuelve `200`.

---

### ST-M10-07 — Non-public GUI access (auth out of scope for demo)
**Persona**: PER-SEC / PER-ADM
**Priority**: Must
**Traces**: FR-GUI-07, NFR-OPS-04
**Story**: Como Security Reviewer, quiero que la GUI no esté expuesta públicamente y que el acceso sea solo por `port-forward`, para no ampliar la superficie de ataque en la demo. La autenticación de operador queda documentada como trabajo futuro.

**Acceptance Criteria**
- **Given** el despliegue por defecto, **When** reviso los Services, **Then** no existe exposición pública (`LoadBalancer`/`NodePort`) para la GUI.
  - **Verification**: `kubectl get svc -n sentinel -o json | jq -e '[.items[] | select(.spec.type=="LoadBalancer" or .spec.type=="NodePort")] | length == 0'` retorna 0.
- **Given** la documentación de despliegue, **When** la reviso, **Then** indica que la GUI se accede solo por `kubectl port-forward` y que la autenticación de operador está fuera del alcance de la demo.
  - **Verification**: `grep -c 'port-forward' docs/deployment.md` devuelve un valor mayor que 0.

---

# PARTE 2 — Enabler Stories

> Historias técnicas que hacen verificables los NFR y sostienen la entrega. No representan funcionalidad de usuario final, pero son necesarias para cumplir el alcance aprobado.

### EN-01 — CI pipeline with lint, tests, build and deploy
**Persona**: PER-ADM / PER-SEC
**Priority**: Must
**Traces**: NFR-OPS-02; PRD §13
**Story**: Como Platform Administrator, quiero un pipeline de CI que ejecute lint, pruebas unitarias e integración, build de imagen, escaneo, helm test y despliegue a kind/k3s, para detectar regresiones antes de fusionar cambios.

**Acceptance Criteria**
- **Given** un pull request, **When** corre el pipeline, **Then** ejecuta todas las etapas y falla si alguna no pasa.
  - **Verification**: el job de CI (GitHub Actions/GitLab CI) muestra las etapas `lint`, `test`, `build`, `scan`, `helm-test`, `deploy` en estado exitoso.
- **Given** un test roto, **When** corre el pipeline, **Then** el pipeline falla y bloquea el merge.
  - **Verification**: `pytest --maxfail=1` retorna exit code distinto de 0 y el status check del PR es `failure`.

---

### EN-02 — Property-based tests for parsing, normalization and baseline
**Persona**: PER-ADM / PER-SEC
**Priority**: Must
**Traces**: NFR-TECH-03; PRD §11.2
**Story**: Como Security Reviewer, quiero pruebas basadas en propiedades para el parseo de Nmap XML, la normalización de flujos y el cálculo de baseline, para detectar errores en entradas no previstas.

**Acceptance Criteria**
- **Given** entradas generadas, **When** se ejecuta la suite PBT, **Then** no se encuentran contraejemplos para las propiedades definidas.
  - **Verification**: `pytest tests/property -k "nmap_xml or flow_normalization or baseline"` pasa.
- **Given** un parser que acepta XML malformado, **When** corre la propiedad de robustez, **Then** el test falla con un contraejemplo mínimo.
  - **Verification**: `pytest tests/property/test_nmap_xml.py` pasa y reporta los casos generados.

---

### EN-03 — Repository documentation
**Persona**: PER-ADM / PER-SEC
**Priority**: Must
**Traces**: NFR-OPS-03; PRD §13
**Story**: Como Platform Administrator, quiero documentación Markdown de arquitectura, despliegue, operación y troubleshooting, para operar Sentinel sin conocimiento tribal.

**Acceptance Criteria**
- **Given** el repositorio, **When** se revisan los documentos, **Then** existen `docs/architecture.md`, `docs/deployment.md`, `docs/operations.md` y `docs/troubleshooting.md`.
  - **Verification**: `for f in architecture deployment operations troubleshooting; do test -f docs/$f.md || exit 1; done` retorna 0.
- **Given** los comandos documentados, **When** se ejecutan literalmente, **Then** son válidos para la versión desplegada.
  - **Verification**: `grep -c 'helm install' docs/deployment.md` devuelve un valor mayor que 0 y el comando coincide con el chart.

---

### EN-04 — Container image vulnerability scan
**Persona**: PER-SEC
**Priority**: Must
**Traces**: NFR-SEC-03; PRD §13
**Story**: Como Security Reviewer, quiero que el pipeline escanee la imagen de Sentinel, para detectar vulnerabilidades antes del despliegue.

**Acceptance Criteria**
- **Given** una imagen construida, **When** corre el escáner, **Then** se publica el informe de vulnerabilidades y el pipeline falla ante severidad crítica configurada.
  - **Verification**: `trivy image --exit-code 1 --severity CRITICAL sentinel:test` con imagen de prueba limpia retorna 0; con imagen vulnerable retorna distinto de 0.
- **Given** el pipeline, **When** se inspeccionan los artefactos, **Then** el informe de escaneo queda adjunto.
  - **Verification**: el artefacto `trivy-report.json` existe en la ejecución de CI.

---

### EN-05 — Hardened Alpine base and non-root containers
**Persona**: PER-SEC / PER-ADM
**Priority**: Must
**Traces**: NFR-SEC-02; PRD §9 M9
**Story**: Como Security Reviewer, quiero que Core, Discovery y Grafana usen base Alpine y usuario no root, para reducir la superficie de ataque.

**Acceptance Criteria**
- **Given** la imagen, **When** se inspecciona, **Then** la base es Alpine.
  - **Verification**: `docker run --rm sentinel:test cat /etc/os-release | grep -c Alpine` retorna 1.
- **Given** los contenedores, **When** se inspecciona el usuario, **Then** no corren como root (excepto el Sensor, que documenta la excepción).
  - **Verification**: `kubectl get pod -n sentinel -l app=sentinel-core -o jsonpath='{.items[0].spec.containers[0].securityContext.runAsNonRoot}'` devuelve `true`.

---

### EN-06 — Ground-truth integration suite GT-01..GT-05
**Persona**: PER-OPR / PER-ADM / PER-SEC
**Priority**: Must
**Traces**: GT-01, GT-02, GT-03, GT-04, GT-05, NFR-OPS-02; PRD §11
**Story**: Como equipo de entrega, quiero una suite de integración con los cinco casos ground truth, para demostrar el comportamiento esperado con evidencia reproducible.

**Acceptance Criteria**
- **Given** el entorno de laboratorio, **When** se ejecuta la suite, **Then** pasan los cinco casos: normal, nuevo host, host ausente, tráfico alto y sensor caído.
  - **Verification**: `pytest tests/integration/test_gt_01_05.py -v` retorna 0.
- **Given** un caso fallido, **When** se ejecuta la suite, **Then** el caso se reporta como fallo y el pipeline se detiene.
  - **Verification**: `pytest tests/integration/test_gt_01_05.py --maxfail=1` retorna distinto de 0 ante un fallo inducido.

---

### EN-07 — Lab performance validation (non-binding)
**Persona**: PER-ADM
**Priority**: Could
**Traces**: NFR-PERF-01, NFR-PERF-02, NFR-PERF-03; PRD §3.1, §3.2
**Story**: Como Platform Administrator, quiero medir en laboratorio el tiempo de descubrimiento, la tasa de flujos y la latencia de la API, para documentar objetivos iniciales no vinculantes.

**Acceptance Criteria**
- **Given** una red /24 de laboratorio, **When** se cronometra el descubrimiento, **Then** se registra el tiempo observado junto al objetivo inicial de 60s.
  - **Verification**: `pytest tests/perf/test_discovery_time.py --report` genera un informe con el tiempo medido.
- **Given** un generador de tráfico, **When** se mide el Sensor, **Then** se registra la tasa observada frente al objetivo de 10k flujos/s.
  - **Verification**: `pytest tests/perf/test_sensor_throughput.py --report` genera un informe con la tasa medida.

---

# PARTE 3 — Traceability Matrix

## 3.1 Requisito funcional → Historia

| Requisito | Historias |
|---|---|
| FR-DISC-01 | ST-M1-02, ST-M2-01 |
| FR-DISC-02 | ST-M1-02, ST-M2-02 |
| FR-DISC-03 | ST-M1-01, ST-M2-01 |
| FR-DISC-04 | ST-M1-03 |
| FR-DISC-05 | ST-M1-04 |
| FR-DISC-06 | ST-M1-01, ST-M10-04 |
| FR-TRAF-01 | ST-M3-01 |
| FR-TRAF-02 | ST-M3-01, ST-M9-03 |
| FR-TRAF-03 | ST-M3-01 |
| FR-TRAF-04 | ST-M3-02 |
| FR-TRAF-05 | ST-M3-03, ST-M4-01 |
| FR-ARP-01 | ST-M3-04 |
| FR-ARP-02 | ST-M3-04 |
| FR-ARP-03 | ST-M3-05, ST-M7-02 |
| FR-ARP-04 | ST-M3-06, ST-M7-03 |
| FR-BASE-01 | ST-M5-01 |
| FR-BASE-02 | ST-M5-01 |
| FR-BASE-03 | ST-M5-02 |
| FR-BASE-04 | ST-M5-03 |
| FR-BASE-05 | ST-M5-04, ST-M7-01, ST-M7-02, ST-M7-03, ST-M7-04 |
| FR-CORE-01 | ST-M4-01, ST-M4-07, ST-M3-03 |
| FR-CORE-02 | ST-M6-01 |
| FR-CORE-03 | ST-M4-02, ST-M8-02 |
| FR-CORE-04 | ST-M4-03 |
| FR-CORE-05 | ST-M4-04, ST-M2-03 |
| FR-EXP-01 | ST-M4-05 |
| FR-EXP-02 | ST-M4-06 |
| FR-EXP-03 | ST-M4-06 |
| FR-OBS-01 | ST-M7-05, ST-M8-01, ST-M6-03 |
| FR-OBS-02 | ST-M6-02, ST-M6-03, ST-M5-04 |
| FR-OBS-03 | ST-M7-06 |
| FR-OBS-04 | ST-M7-05 |
| FR-SEC-01 | ST-M9-02 |
| FR-SEC-02 | ST-M9-02 |
| FR-SEC-03 | ST-M9-01 |
| FR-SEC-04 | ST-M9-03 |
| FR-GUI-01 | ST-M10-01 |
| FR-GUI-02 | ST-M10-02 |
| FR-GUI-03 | ST-M10-03 |
| FR-GUI-04 | ST-M10-04 |
| FR-GUI-05 | ST-M10-05 |
| FR-GUI-06 | ST-M10-06 |
| FR-GUI-07 | ST-M10-07 |
| FR-GUI-08 | ST-M10-01, ST-M10-02 |

## 3.2 Requisito no funcional → Historia

| Requisito | Historias |
|---|---|
| NFR-PERF-01 | EN-07 |
| NFR-PERF-02 | EN-07 |
| NFR-PERF-03 | EN-07 |
| NFR-AVAIL-01 | ST-M7-04 |
| NFR-AVAIL-02 | ST-M4-02 |
| NFR-SEC-01 | ST-M9-04, EN-04 |
| NFR-SEC-02 | EN-05, ST-M9-03 |
| NFR-SEC-03 | EN-04 |
| NFR-OPS-01 | ST-M1-01 |
| NFR-OPS-02 | EN-01, EN-06 |
| NFR-OPS-03 | EN-03 |
| NFR-TECH-01 | ST-M8-01, ST-M8-02, ST-M8-03 |
| NFR-TECH-02 | ST-M8-04 |
| NFR-TECH-03 | EN-02 |
| NFR-TECH-04 | ST-M10-01..07 |
| NFR-OPS-04 | ST-M10-07 |
| NFR-OPS-05 | ST-M10-06 |

## 3.3 Ground truth → Historia

| Caso | Historia principal |
|---|---|
| GT-01 Normal operation | EN-06, ST-M2-01, ST-M5-01 |
| GT-02 New host | EN-06, ST-M2-03 |
| GT-03 Host absent | EN-06, ST-M2-04 |
| GT-04 High traffic | EN-06, ST-M7-01 |
| GT-05 Sensor down | EN-06, ST-M7-04 |

## 3.4 Eventos y reglas → Historia

| Elemento | Historia |
|---|---|
| E-01 AssetFirstSeen | ST-M2-03 |
| E-02 AssetMissing | ST-M2-04 |
| E-03 PortServiceChanged | ST-M2-05 |
| E-04 ArpMappingChanged | ST-M3-06, ST-M7-03 |
| E-05 TrafficWindowObserved | ST-M3-02, ST-M3-03 |
| E-06 SensorUnavailable | ST-M7-04 |
| E-07 DiscoveryCycleFailed | ST-M2-06, ST-M1-02 |
| R-01 TrafficThresholdExceeded | ST-M7-01 |
| R-02 ArpRateThresholdExceeded | ST-M3-05, ST-M7-02 |
| R-03 ArpMappingChanged | ST-M3-06, ST-M7-03 |
| R-04 SensorUnavailable | ST-M7-04 |

---

# PARTE 4 — Persona → Story Map

| Persona | Historias |
|---|---|
| PER-OPR | ST-M1-01, ST-M1-02, ST-M1-04, ST-M2-01..06, ST-M3-01..06, ST-M4-01..07, ST-M5-01..04, ST-M6-01..02, ST-M7-01..06, ST-M10-01..06, EN-06 |
| PER-ADM | ST-M1-01, ST-M1-03, ST-M1-04, ST-M2-01, ST-M2-06, ST-M3-02, ST-M3-03, ST-M4-01..03, ST-M5-02, ST-M5-04, ST-M6-01, ST-M6-03, ST-M7-04..06, ST-M8-01..04, ST-M9-01..03, ST-M10-04, ST-M10-05, ST-M10-07, EN-01, EN-03, EN-05..07 |
| PER-SEC | ST-M1-02, ST-M3-06, ST-M4-03, ST-M4-05, ST-M4-06, ST-M6-02, ST-M7-03, ST-M9-01..04, ST-M10-03, ST-M10-06, ST-M10-07, EN-01, EN-02, EN-04, EN-05, EN-06 |

---

# PARTE 5 — Compliance Checklist

## 5.1 INVEST

| Criterio | Cumplimiento |
|---|---|
| Independent | Cada historia se puede implementar y verificar por separado; las dependencias se expresan en la matriz. |
| Negotiable | El cuerpo describe valor; los detalles de implementación quedan para diseño. |
| Valuable | Cada historia traza a una persona y a un requisito aprobado. |
| Estimable | Alcance acotado y criterios verificables. |
| Small | Historias por módulo, con un objetivo verificable cada una. |
| Testable | Toda historia tiene al menos un comando o comprobación medible. |

## 5.2 Scope lock (sin IA)

Verificación: no existe mención de agente, LLM, Tool Layer, orquestación IA ni confirmación humana de operaciones en las historias funcionales ni en los enablers.

- **Verification**: `awk '/^# PARTE 1/{p=1} /^# PARTE 5/{p=0} p' aidlc-docs/inception/user-stories/stories.md | grep -c -iE "\b(agente|llm|tool layer|orquestaci[oó]n ia|confirmaci[oó]n humana)\b"` retorna 0 (solo las secciones de control mencionan estos términos).

## 5.3 Anti-requisitos

| Anti-requisito | Evidencia |
|---|---|
| AR-AI-01..05 | Ninguna historia incorpora IA/LLM/agente/orquestación. |
| Sin respuesta automática (PRD §6.9) | ST-M9-04 prueba ausencia de escrituras; ST-M7-01/02 evitan atribución de ataque. |
| Sin payload (PRD §6.6) | ST-M3-01 prueba que no se almacena payload. |

---

# PARTE 6 — Approval Gate

**Estado**: APPROVED — re-aprobado por defecto (2026-11-07T16:25:32Z).
**Siguiente etapa**: Application Design (execution plan actualizado y re-aprobado).

**Change log**:
- 2026-11-07T16:25:32Z: Added module M10 (7 GUI/report stories: ST-M10-01..07), FR-DISC-06 traceability, NFR-TECH-04 / NFR-OPS-04 / NFR-OPS-05 traces, and updated persona→story map. Re-approved by default per user instruction; recorded in `audit.md`.
