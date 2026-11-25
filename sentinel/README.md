# Sentinel

Plataforma self-hosted de monitoreo de activos de red sobre Kubernetes, con un agente de IA que guía al operador.

## Requisitos

- Python 3.11 (fijado: `>=3.11,<3.12`)
- Docker (para la imagen OCI)
- kind/k3s (despliegue — ver U9)

## Instalación

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Estructura

```text
src/sentinel/foundation/      # librería compartida: models, errors, config, logging, retry, metrics
src/sentinel/core/            # Core (U2): api, ingestion, inventory, query, export, health, discovery, db, metrics
src/sentinel/gui/             # GUI del operador (U3): vistas /ui, reporte MD/PDF, cliente loopback
tests/unit/foundation/        # tests unitarios de foundation
tests/unit/core/              # tests unitarios del Core (API con TestClient)
tests/unit/test_correlation.py  # ST-M4-04 correlación
tests/unit/test_normalization.py # ST-M4-04 normalización MAC
tests/property/               # property-based tests (hypothesis)
tests/integration/            # tests de integración (persistencia, idempotencia, logs, filtros, export)
tests/unit/gui/               # tests unitarios de la GUI (vistas, reporte, static/BR)
tests/integration/gui/        # integración GUI ↔ Core real (loopback en proceso)
tests/fixtures/               # fixtures compartidos (observations.json)
Dockerfile                    # imagen única Alpine, usuario no-root
```

## Core (U2) — API interna

```bash
# arranque local (uvicorn 1 worker en 0.0.0.0:8080 + métricas en 9108)
export SENTINEL_DB_PATH=./dev.db
export SENTINEL_INGEST_TOKEN=$(openssl rand -hex 32)   # Bearer de POST /ingest
python -m sentinel.core
# o en dev sin token: uvicorn sentinel.core.api.app:app --reload --port 8080
```

Configuración (`.env.example`): `SENTINEL_DB_PATH`, `SENTINEL_INGEST_TOKEN`,
`SENTINEL_PAGE_LIMIT`, `SENTINEL_MISSING_CYCLES` (+ claves comunes de foundation).

Endpoints (`/api/v1`):

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/ingest` | Bearer | Lote de observaciones ⇒ `202 IngestResult` |
| GET | `/assets` | — | Inventario paginado (`status`, `limit`, `offset`) |
| GET | `/assets/{asset_id}` | — | Detalle de activo |
| GET | `/events` | — | Eventos (`from`, `to`, `asset_id`, `rule`, `severity`) |
| GET | `/alerts` | — | Alertas (`from`, `to`, `state`) |
| GET | `/health` | — | Estado derivado de la BD |
| GET | `/export` | — | CSV/JSON bajo demanda (`format`, `from`, `to`) |
| POST | `/discovery` | — | Disparo manual (`202` / `409` / `503` sin runner) |
| GET | `/discovery/{run_id}` | — | Estado del ciclo |

- **Métricas**: servidor propio `GET :9108/metrics` con las **14 familias** `sentinel_*` del contrato v2 (ver «Métricas (U7)»).
- **Evidencia**: cada observación/evento emite una línea JSON a stdout
  (`kind ∈ {observation,inference,event,alert}` + campos de evidencia).

## GUI de operador (U3) — `/ui` + reporte

La GUI se sirve desde el mismo proceso/`8080` del Core (misma app: `uvicorn\ sentinel.core.api.app:app --port 8080` o `python -m sentinel.core`;
sin auth en el MVP;
acceso de lab **solo** vía `kubectl port-forward` — FR-GUI-07, sin
LoadBalancer/NodePort). Consume la API por loopback (`http://127.0.0.1:8080`),
nunca la base de datos.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/ui/assets` | Inventario paginado (`page`, `status`) |
| GET | `/ui/assets/{asset_id}` | Detalle (observaciones, eventos, tráfico, ARP) |
| GET | `/ui/events` | Línea de tiempo eventos+alertas (`from`, `to`, `asset_id`, `rule`, `severity`) |
| GET | `/ui/alerts` | Solo alertas |
| GET | `/ui/health` | Salud (sensores con heartbeat caído) |
| GET/POST | `/ui/discovery` | Disparo de discovery (polling con backoff en el cliente) |
| GET | `/ui/report` | Reporte `format=md\|pdf` (`from`/`to` requeridos) |
| GET | `/api/v1/report` | Mismo reporte por la API (contrato C7) |
| GET | `/static/*` | htmx + Tailwind/DaisyUI vendorizados (sin CDN) |

```bash
# acceso de lab (ST-M10-07)
kubectl -n <ns> port-forward svc/sentinel-core 8080:8080

# reporte MD (ST-M10-06)
curl -o report.md "http://localhost:8080/ui/report?from=2026-01-01&to=2026-01-31"
curl -o report.pdf "http://localhost:8080/api/v1/report?from=2026-01-01&to=2026-01-31&format=pdf"

# export (botón de la GUI → endpoint de U2)
curl "http://localhost:8080/api/v1/export?format=csv&from=2026-01-01&to=2026-01-31"
```

## Discovery (U4) — escáner de red

Ciclo `arp → icmp → tcp → nmap` con deadline, allowlist de alcance y una
ingesta única por ciclo (`reconcile` según estado). Paquete
`src/sentinel/discovery/` (worker standalone + runner in-process del Core).

```bash
# ciclo único sobre la allowlist (exit 0/1)
export SENTINEL_DISCOVERY_HOSTS=10.0.0.0/24,192.168.1.0/24   # o CIDRS en modo cidr
export SENTINEL_INGEST_TOKEN=$TOKEN                            # Bearer de POST /ingest
python -m sentinel.discovery --once

# en loop (CronJob U9 usa --once; el loop es para lab/servidor continuo)
python -m sentinel.discovery --loop --interval 15
```

Configuración (`SENTINEL_DISCOVERY_*`, loader estricto: clave desconocida ⇒
`ConfigError` al arrancar):

| Variable | Default | Descripción |
|---|---|---|
| `SENTINEL_DISCOVERY_SCOPE_MODE` | `explicit_hosts` | `explicit_hosts` (match exacto) o `cidr` |
| `SENTINEL_DISCOVERY_HOSTS` | `""` | Allowlist CSV (obligatoria en modo `explicit_hosts`) |
| `SENTINEL_DISCOVERY_CIDRS` | `""` | Redes CSV (obligatoria en modo `cidr`) |
| `SENTINEL_DISCOVERY_PORTS` | `22,80,443` | Allowlist de puertos (única que se escanea) |
| `SENTINEL_DISCOVERY_INTERVAL_MIN` | `15` | Intervalo del `--loop` (minutos) |
| `SENTINEL_DISCOVERY_TIMEOUT_SECONDS` | `30` | Deadline global del ciclo |
| `SENTINEL_DISCOVERY_SCANNER` | `auto` | `auto` \| `nmap` \| `fixtures` |
| `SENTINEL_DISCOVERY_NMAP_ARGS` | `""` | Flags extra (whitelist estricta: sin `-O/-sU/-sS/-A/--script`) |
| `SENTINEL_INGEST_TOKEN` | — | Bearer hacia `POST /api/v1/ingest` |
| `SENTINEL_API_BASE` | `http://127.0.0.1:8080` | URL del Core (en K8s U9 inyecta `http://sentinel-core:8080`) |

- **Fallback fixtures** (`auto`): si el binario `nmap` no está presente se usa
  `FixtureScanner` con dataset de lab + log `scanner_fallback` (el ciclo no
  falla por falta del binario). La imagen OCI incluye `nmap` (ID-U4-01).
- **Métricas**: `sentinel_discovery_cycles_total` / `..._failed_total` en el
  servidor `:9108/metrics` del Core (ruta in-process); la ruta standalone
  solo emite logs (`discovery_cycle_failed`, FQ1=C).
- **Handoff U9/U10** (ID-U4-02/05): CronJob `--once` cada 15 min
  (`concurrencyPolicy: Forbid`, `restartPolicy: Never`), env desde
  `values.yaml`, egress restringido a DNS + `sentinel-core:8080` +
  alcance; sin Service/puerto/probe/PVC para el worker.
- **Documented-only (D-U4-08)**: `sensor_id` configurable (default
  `sensor-0`, ST-M1-03), SNMP opcional (ST-M1-04), `PortServiceChanged`
  (ST-M2-05) — sin código en U4.

## Traffic Sensor (U5) — ventanas de tráfico + ARP

Sensor de ventana tumbling epoch-aligned (`[floor(now/W)*W, +W)`) en
`src/sentinel/traffic/`: fuente → agregador → ARP → `IngestClient` batch →
Core (U2). 1 POST por ventana (`window_id` uuid5 dedup, BR-U5-23/27), sin
clave `reconcile` (BR-U5-25), lotes ≤1000 (BR-U5-24), sin pérdida en el
borde de ventana (evento pendiente se atribuye a la siguiente) y sin buffer
local: si el export falla la ventana se descarta con log
`sensor_export_failed` (BR-U5-28).

```bash
# ventana única (exit 0 emitida / 1 error de config o export)
export SENTINEL_TRAFFIC_WINDOW_SECONDS=5
export SENTINEL_INGEST_TOKEN=$TOKEN
python -m sentinel.traffic --once

# loop continuo (sigue tras ventanas fallidas; SIGTERM limpia entre ventanas)
python -m sentinel.traffic --loop
```

Configuración (`SENTINEL_TRAFFIC_*`, loader estricto: clave desconocida ⇒
`ConfigError` al arrancar; `WINDOW_SECONDS` ∈ {1,5,10,30,60}):

| Variable | Default | Descripción |
|---|---|---|
| `SENTINEL_TRAFFIC_WINDOW_SECONDS` | `5` | Tamaño de ventana tumbling |
| `SENTINEL_TRAFFIC_INTERFACE` | `eth0` | Interfaz lógica de las observaciones |
| `SENTINEL_TRAFFIC_SENSOR_ID` | `sensor-0` | `sensor_id` de cada observación (heartbeat) |
| `SENTINEL_TRAFFIC_SIM_SEED` | `42` | Semilla de `SimulatedSource` (determinista) |
| `SENTINEL_TRAFFIC_SIM_RATE` | `100.0` | Paquetes/segundo simulados (>0) |
| `SENTINEL_TRAFFIC_FALLBACK` | `true` | `false` ⇒ exige fuente real, `ConfigError` sin ella |
| `SENTINEL_INGEST_TOKEN` | — | Bearer hacia `POST /api/v1/ingest` |
| `SENTINEL_API_BASE` | `http://127.0.0.1:8080` | URL del Core (K8s: `http://sentinel-core:8080`) |

- **Fuentes**: `SimulatedSource` (determinista, lab/CI) y `FixtureSource`
  (JSON de prueba); la captura real AF_PACKET es **documented-only**
  (BR-U5-33) — sin scapy ni dependencias de captura en `src/` ni en
  `requirements.txt` (verificado en `tests/unit/traffic/test_boundaries.py`).
- **Heartbeat factual**: toda ventana emitida porta `sensor_id`; ventana
  vacía ⇒ 1 observación cero `protocol="other"` (red idle ≠ sensor caído,
  D-U5-01/GT-05). `arp_messages_per_second` se loguea al cerrar cada ventana.
- **ARP → U2**: solo exporta `ArpObservation` crudas; el tracking IP↔MAC y
  `arp_mapping_changed` lo decide `InventoryService` de U2
  (BR-U5-20/21, `create_if_missing=False` no crea activos).
- **Mapeo de protocolos**: tcp/udp/icmp/other desde números IP; IPv6 se
  descarta; `pairs` acotado a 100 y orden determinista (BR-U5-16).

## Baseline & conditions (U6) — R-01 / GT-04

`src/sentinel/baseline/` evalúa la regla determinista **R-01**
(`bytes_per_second > μ + k·s`, comparación estricta) sobre las series que
llegan al Core. El hook `on_accepted` de `IngestionService` (post-commit,
FD §3.2) empuja solo las observaciones aceptadas al `ConditionService`
(`app.state.condition`), que jamás rompe el 202 (BR-U6-15).

Flujo por serie (`<metric>|<interface>|<protocol>`, p. ej.
`bytes_per_second|eth0|tcp`):

1. **5 muestras** (`BASELINE_SAMPLES`) ⇒ baseline congelada (μ y s² n-1
   sin recálculo, ST-M5-01/02).
2. **Supresión prioritaria** `t_first + 5×interval` (25 s con interval=5):
   dentro de la ventana no se emite alerta aunque se supere el absoluto
   (FR-BASE-04, ST-M5-03).
3. **Umbral efectivo**: establecida ⇒ `μ + k·s`; no establecida ⇒
   `ABSOLUTE_BPS` si está configurado, si no `no_data`.
4. `firing` ⇒ fila en `alerts` (uuid5 estable, BR-U6-17); una observación
   posterior por debajo ⇒ `resolved` en la **misma** fila; re-activación ⇒
   fila nueva con `alert_id` distinto.
5. Hidratación al arrancar (`create_app`): fallo de BD ⇒ log
   `baseline_hydration_failed` + servicio vacío (arranque OK, P2).

Configuración (`SENTINEL_BASELINE_*`, loader estricto fail-fast — clave
desconocida o rango inválido ⇒ `ConfigError` al arrancar):

| Variable | Default | Descripción |
|---|---|---|
| `SENTINEL_BASELINE_K` | `3.0` | Multiplicador de desviación (>0) |
| `SENTINEL_BASELINE_ABSOLUTE_BPS` | — | Umbral absoluto de respaldo; **obligatorio en `values.yaml`** (U9, ID-U6-07) — sin default numérico en código (PRD §3.3) |
| `SENTINEL_BASELINE_INTERVAL_SECONDS` | `5` | Intervalo nominal de las series (≥1) |
| `SENTINEL_BASELINE_COLLECTOR_TIMEOUT_SECONDS` | `300` | Heartbeat del collector para `sentinel_collector_up` (≥1) |

- **Eventos** (`component=baseline.*`): `baseline_established`,
  `condition_firing`, `condition_resolved`, `condition_evaluation_failed`,
  `baseline_hydration_failed`, `condition_persistence_failed`.
- **Indicadores** (hacia U7): `sentinel_traffic_threshold_exceeded`,
  `sentinel_baseline_status`, `sentinel_baseline_established`,
  `sentinel_collector_up` (catálogo en `foundation/metrics_contract.py`).
- **Frontera** (BR-U6-01): `baseline/` importa solo `sentinel.foundation*`
  y stdlib — nunca `sentinel.core` ni `sqlite3`; los adaptadores viven en
  `core/baseline_wiring.py` (verificado en `tests/unit/baseline/test_boundaries.py`).
- **ST-M5-01..04 documented-only**: el código generado es el soporte
  mínimo de R-01/GT-04; la instrumentación completa es M5 posterior.

## Métricas (U7) — `GET :9108/metrics`

Exposición Prometheus del Core (servidor propio, sin dependencia del stack de
observabilidad). Catálogo v2 en `src/sentinel/foundation/metrics_contract.py`:

| Familia | Tipo | Fuente |
|---|---|---|
| `sentinel_discovery_cycles_total` / `..._failed_total` | counter | contador en proceso (U4) |
| `sentinel_api_requests_total` | counter | middleware API (`state` = status) |
| `sentinel_flows_total` / `sentinel_arp_messages_total` | counter | hook post-commit de ingesta (U5) |
| `sentinel_bytes_per_second` | gauge | última ventana por `interface`/`protocol` (SQLite) |
| `sentinel_alerts_firing` | gauge | `alerts.state='firing'` (SQLite) |
| `sentinel_assets_total` / `sentinel_asset_changes_total` | gauge/counter | inventario + eventos (SQLite) |
| `sentinel_baseline_established` / `..._status` / `..._traffic_threshold_exceeded` | gauge | `ConditionService` (U6) |
| `sentinel_collector_up` / `..._heartbeat_age_seconds` | gauge | heartbeat de sensores |

- **Labels** (allowlist): `component`, `protocol`, `interface`, `rule`, `state`,
  `collector`, `metric`. Prohibidos por cardinalidad: `src_ip`, `dst_ip`, `mac`,
  `asset_id`. Cada muestra se valida con `assert_allowed()` (denylist +
  allowlist) y una familia desconocida falla el scrape.
- **Zero-fill**: toda familia sin muestra se emite en `0` (`component=core`),
  de modo que el conjunto de familias es siempre el catálogo completo.
- **Contadores post-commit**: solo observaciones aceptadas alimentan
  `flows_total`/`arp_messages_total`; reenvíos deduplicados no duplican.
  Los contadores se reinician con el proceso (Prometheus absorbe el reset).
- **ServiceMonitor**: `deploy/monitoring/servicemonitor.yaml` (namespace
  `sentinel`, selector `app.kubernetes.io/name: sentinel-core`, puerto
  `metrics`). Se aplica fuera de banda con `kubectl apply -f`; el Service con
  el puerto `metrics` llega con el stack de U8/U9.

## Comandos de calidad (los mismos que CI)

```bash
ruff check . && ruff format --check .   # lint + formato
mypy src/sentinel                        # tipos (gradual)
pytest tests/unit tests/property tests/integration -q \
  --cov=sentinel --cov-fail-under=70 --cov-report=term-missing
coverage report --include='*/gui/*' --fail-under=70   # gate doble de GUI (P8)
coverage report --include='*/discovery/*' --fail-under=70  # gate discovery (P11)
coverage report --include='*/traffic/*' --fail-under=70    # gate traffic (U5, P11)
coverage report --include='*/baseline/*' --fail-under=70   # gate baseline (U6, P13)
docker build -t sentinel:test .         # imagen OCI
```

CI (GitHub Actions): `.github/workflows/ci.yml` en la raíz del repositorio —
jobs `lint` → `test` → `build` (sin caché ni artifacts).

## Documentación de diseño

Los artefactos de diseño y trazabilidad viven en `aidlc-docs/`
(requisitos, historias, planes por unidad, auditoría).
