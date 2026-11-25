# Functional Design Plan — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — Functional Design (Parte 1: Planning)
**Fecha**: 2026-11-16
**Estado**: GENERATED — Q1–Q16 = A; FQ1 = C (2026-11-16); artefactos FD generados; pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/` (scope C12, ARP/ICMP/TCP + Nmap, worker de ciclo, ingesta al Core)
**Entradas**: `unit-of-work.md` (§U4), `unit-of-work-story-map.md` (ST-M1-01..04, ST-M2-01..06), `stories.md` (AC), `requirements.md` (FR-DISC-01..06, NFR-TECH-03), `component-methods.md` (§7 DiscoveryService, §8 Scope & Config Validator), `services.md` (§2.1, §2.2, §4), `components.md` (C9, C12), `implementation-scope.md`, contratos de U1+U2 aprobados (`DiscoveryTrigger`, `DiscoveryObservation`, `ScopeError` sin levantar, handler 400 `scope_violation` ya presente en U2).

---

## 1. Contexto de la unidad (Step 1 — analizado)

- **Responsabilidad**: configuración de alcance (C12), descubrimiento ARP/ICMP/TCP + Nmap `-sT -sV --version-light` sobre allowlist, worker de ciclo (CronJob/manual), normalización del lote y envío por HTTP al Core, manejo de fallos de ciclo (`DiscoveryCycleFailed` + métrica de fallos).
- **Historias**: ST-M1-01, ST-M1-02, ST-M2-01..04, ST-M2-06 (implementadas); ST-M1-03, ST-M1-04, ST-M2-05 (documented-only según `unit-of-work.md`).
- **Frontera**: el worker **no abre SQLite**, no evalúa condiciones y no escanea fuera de la allowlist; solo importa `foundation` y habla con Core por HTTP; la reconciliación `first_seen`/`missing` pertenece a U2 (`InventoryService`, ya generado).
- **Depende de**: U2 (aprobado): `POST /api/v1/ingest`, `POST /api/v1/discovery` + `DiscoveryTrigger` con protocolo `CycleRunner.run(hosts, timeout_seconds) -> hosts_seen`, estados `completed|timeout|failed`, lock único (409), handler `scope_violation` 400 **sin trigger** (U4 debe levantarlo).
- **Lo que U2 NO hace y U4 debe diseñar**: validación de scope (worker y/o API), fuente de configuración del worker (hoy no existe `src/sentinel/discovery/` ni claves `SENTINEL_DISCOVERY_*`), estrategia de escaneo real vs fixtures (nmap puede faltar; non-root ⇒ ARP/ICMP sin raw sockets), programación periódica (U9 aún no tiene chart; Dockerfile documenta `python -m sentinel.discovery`), ingest batching/retry, quién incrementa `sentinel_discovery_cycles_failed_total` (familia aún no está en `METRIC_FAMILIES`), y qué hacer con ciclos parciales/timeout frente a `reconcile_missing` de U2 (BR-U2-15: solo ciclos `completed` cuentan para ausencia).
- **Open questions que esta etapa cierra**: dónde se valida el scope, fuente de configuración, estrategia de escaneo/fixtures, programación, ingesta, timeout/parciales, contrato de reconcile, métrica/log de fallos, flags prohibidos, defaults de scope, modelo de dominio del worker, frontera con U2, `sensor_id`, documented-only (SNMP/port change), estructura de paquete + wiring del runner, semántica de `hosts_seen`.
- **Categoría Frontend**: **no aplica** a U4 (sin UI; U3 es la única unidad con UI).

---

## 2. Checklist del plan

- [x] Analizar unidad, historias y restricciones
- [x] Generar preguntas de diseño funcional (Q1–Q16)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-16: "Acepto todo" ⇒ Q1–Q16 = A)
- [x] Analizar respuestas y resolver ambigüedades — 1 interacción Q4×Q8 sin canal de reporte para ciclos standalone ⇒ follow-up FQ1
- [x] Generar `business-logic-model.md`, `business-rules.md`, `domain-entities.md` en `construction/u4-discovery/functional-design/` (FQ1=C incorporada: D-U4-01)
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de diseño funcional

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Dónde se valida el scope autorizado (C12, ST-M1-02, services.md §4)

Contexto: ST-M1-02 AC1 exige que el Job termine **sin enviar paquetes** y registre `DiscoveryCycleFailed` con causa `scope_violation`; `services.md` §4 dice "Host fuera de alcance → `400` + `scope_violation` → no se ejecuta el sondeo"; U2 ya tiene el handler 400 `scope_violation` pero **nadie levanta `ScopeError`**; el CronJob (U9) invocará el worker directamente, sin pasar por la API.

A) **Ambos**: el worker valida cada target contra la allowlist antes de sondear (fuera de alcance ⇒ sin paquetes, log `scope_violation`, run `failed`) **y** `POST /api/v1/discovery` valida el host de la request y devuelve 400 `scope_violation` antes de crear el run (edición acotada de U2; cumple services.md §4 literal y ST-M1-02 para ambos disparos) *(recomendado)*

B) Solo en el worker: la API crea el run y el ciclo falla después (desvío de services.md §4 "no se ejecuta el sondeo")

C) Solo en la API: el CronJob bypassaría la validación (no cumple ST-M1-02 para el flujo programado)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 2 — Fuente de configuración del worker en el MVP (ST-M1-01, FR-DISC-03/06)

Contexto: los Helm values llegan en U9 (hoy no hay chart); `CoreSettings` de U1 tiene **exactamente 4 claves `SENTINEL_*`** (BR sin claves nuevas para el Core); U9 mapeará values → env del worker.

A) **Variables de entorno propias del worker** `SENTINEL_DISCOVERY_*` (scope.mode, scope.hosts, scope.ports, interval, timeout, snmp… según respuestas) con loader propio en `discovery/config.py` + defaults de laboratorio; `CoreSettings` sigue intacto con sus 4 claves *(recomendado)*

B) Solo CLI args de `python -m sentinel.discovery` (`--hosts`, `--ports`, `--interval`…), sin variables de entorno

C) Archivo de configuración YAML/JSON montado como volumen

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 3 — Estrategia de escaneo ARP/ICMP/TCP + Nmap (FR-DISC-01/02, NFR-TECH-03)

Contexto: contenedor **non-root** (sin raw sockets para ARP/ICMP clásicos); el binario `nmap` puede no estar instalado en la imagen de laboratorio; NFR-TECH-03 exige **PBT sobre el XML de nmap**; `implementation-scope.md` menciona fixtures Nmap/ARP; GT-02/GT-03 exigen inventario poblado en la demo.

A) **Protocolo `Scanner` intercambiable**: `NmapScanner` (invoca `nmap -sT -sV --version-light -p <puertos> -oX -` si el binario existe; TCP connect vía Python stdlib; ARP vía tabla del sistema `ip neigh`/`arp -a`) + `FixtureScanner` (XML/ARP fixtures para tests y demo); si falta el binario ⇒ fallback a fixtures con log advertencia *(recomendado)*

B) Solo fixtures en el MVP (parser + PBT sobre fixtures; sin binario nmap en runtime; demo con datos simulados)

C) nmap obligatorio (si falta el binario ⇒ el ciclo falla)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 4 — Programación periódica del ciclo (FR-DISC-03, ST-M1-01/02, Dockerfile)

Contexto: default 15 min; U9 aún no existe (el CronJob llega con el chart); el Dockerfile de U1 documenta `python -m sentinel.discovery`; la demo sin chart debe poder ejecutar ciclos.

A) CLI con dos modos: `--once` (un ciclo y sale; lo usará el CronJob de U9 y los tests) y `--loop --interval <min>` (demo sin chart); ambos comparten el mismo worker *(recomendado)*

B) Solo `--once` (el loop lo aportará el CronJob de U9; en la demo los ciclos se disparan desde la GUI/manualmente)

C) Loop in-process dentro del Core (hilo en la API que dispara ciclos)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 5 — Ingesta de hallazgos al Core (data flow, services.md §2.1)

Contexto: services.md §2.1 "normaliza lote → POST /api/v1/ingest"; patrón de servicios: "Si el Core no responde, reintenta con backoff hasta lograrlo"; `foundation.retry` ya existe; un ciclo puede tocar muchos hosts.

A) **Un solo `POST /api/v1/ingest` por ciclo** con lote de `DiscoveryObservation` (uno por host visto, con todos los puertos combinados y `method`/`sensor_id` correctos), Bearer `SENTINEL_INGEST_TOKEN`, con reintento/backoff transitorio (si el Core sigue caído ⇒ el ciclo queda `failed` sin perder el lote en tránsito) *(recomendado)*

B) Un `POST` por host encontrado (más granular, más round-trips)

C) Ingestas por fase (ARP primero, luego TCP, luego Nmap)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 6 — Timeout del ciclo y observaciones parciales (services.md §4, ST-M2-06)

Contexto: services.md §4: "Timeout de discovery → Estado `timeout` → **Se conservan observaciones parciales**"; `DiscoveryRequest.timeout_seconds` default 30 (máx 3600); el runner de U2 solo devuelve `hosts_seen` al final.

A) **Deadline por fases**: el worker chequea el tiempo entre fases (arp → tcp → nmap); al agotarse, ingiere **lo ya acumulado** y el ciclo termina en `timeout` (hallazgos parciales conservados en el Core) *(recomendado)*

B) Todo-o-nada: si el ciclo no termina dentro del timeout, no se ingiere nada

C) El worker mata el ciclo y luego ingiere un lote "final" aunque el timeout ya venció (sin distinción de deadline)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 7 — Ciclos parciales/timeout vs reconciliación de ausencias (ST-M2-04 AC2, BR-U2-15)

Contexto: U2 (`InventoryService.reconcile_missing`) incrementa `miss_count` **en todo lote que contiene `DiscoveryObservation`**; BR-U2-15/ST-M2-04 exigen que **solo ciclos `completed`** cuentan para ausencia y que un ciclo fallido/parcial **no** marque `missing`; services.md §4 exige conservar los parciales. Con N=2, dos parciales seguidos marcarían `missing` si el reconcile corre normal.

A) **Contrato acotado**: campo opcional `reconcile: bool = true` en el body de `POST /ingest` (edición acotada de `foundation.Batch` + U2, retrocompatible); U4 envía `reconcile:false` en lotes de ciclos `partial`/`timeout` (se conservan observaciones y `last_seen`, no se incrementa ausencia); ciclos `completed` ⇒ `reconcile:true`; ciclos `failed` ⇒ sin lote *(recomendado; cumple literal ST-M2-04 AC2 y BR-U2-15)*

B) Sin cambio de contrato: parciales/timeout ingieren normal y el reconcile corre (acepta desviación en cascada de BR-U2-15: dos parciales seguidos pueden marcar `missing`)

C) Los parciales **no** se ingieren (conserva el umbral de ausencia, pero pierde "se conservan observaciones parciales" de services.md §4)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 8 — `DiscoveryCycleFailed` y métrica de fallos (ST-M2-06, E-07)

Contexto: el AC exige log `"event":"DiscoveryCycleFailed"` **y** `sentinel_discovery_cycles_failed_total ≥ 1` en `/metrics` (9108, endpoint de U7); `EventType.DISCOVERY_CYCLE_FAILED` existe en `foundation/events.py` pero **nadie lo emite**; la familia de métrica **no** está en `METRIC_FAMILIES` (U1); el Core (`DiscoveryTrigger._execute`) es quien conoce el estado final `failed|timeout`.

A) El **Core** al finalizar un run `failed`/`timeout`: incrementa `sentinel_discovery_cycles_failed_total` (nueva familia añadida a `METRIC_FAMILIES` en foundation — edición acotada de U1) y emite el log `event=discovery_cycle_failed` con causa; `completed` no incrementa *(recomendado)*

B) El worker loguea el fallo y publica su propio endpoint de métricas en otro puerto (complica U7: dos fuentes de métricas)

C) Solo log de causa, sin contador nuevo (no cumple el AC de `/metrics`)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 9 — Validación de métodos de escaneo prohibidos (ST-M1-02 AC2, ST-M2-02)

Contexto: verification `pytest tests/unit/test_config_validation.py -k forbidden_scan_methods` y `tests/unit/test_nmap_args.py -k no_aggressive_flags`; FR-DISC-02 prohíbe `-O`, NSE, UDP y modo agresivo; los argumentos de nmap hoy no existen en código.

A) **`validate_scan_options` en `discovery/config.py`**: whitelist estricta de flags constructibles (`-sT`, `-sV`, `--version-light`, `-p`, `-oX`, `-Pn` si se necesita) que rechaza `-O`, `-sU`, `-sS`, `-sC`, `--script*`, `-A` y cualquier flag fuera de lista; los argumentos de nmap se **construyen programáticamente** (nunca string crudo del usuario) *(recomendado)*

B) Solo blacklist explícita de `-O`, `-sU`, `-sC`, `--script`, `-A` (otros flags ajenos pasarían)

C) Validación documentada en el FD sin test unitario (no cumple la verification de ST-M1-02)

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 10 — Defaults de scope y fail-fast (FR-DISC-06, GT-02, BR)

Contexto: GT-02 requiere "añadir host a `explicit_hosts`" (implica allowlist explícita); sin allowlist no debe sondearse nada; FR-DISC-01 fija métodos; el intervalo default es 15 min y el timeout 30 s.

A) **Allowlist vacía por defecto**: `scope.hosts`/`scope.cidrs` sin valores ⇒ `ConfigError` fail-fast al iniciar el worker (nada se sondea sin allowlist explícita); puertos default `22,80,443`; interval 15 min; timeout 30 s *(recomendado)*

B) Defaults de laboratorio embebidos (p. ej. `192.0.2.0/24`) para que la demo funcione sin ninguna configuración

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 11 — Modelo de dominio del worker (Domain Model)

Contexto: U4 necesita estructurar hallazgos antes de convertirlos en `DiscoveryObservation` (U1); `unit-of-work.md` pide "colectores solo importan `foundation`"; el modelo U1 ya fija el contrato de salida.

A) **Entidades puras sin I/O** en `discovery/domain.py`: `ScopeConfig(mode, hosts, cidrs, ports)`, `ScanTarget`, `HostFinding(ip, mac, hostname, ports[], method, os)`, `CycleResult(findings, hosts_seen, partial, error)` → mapeo final a `DiscoveryObservation` en el cliente de ingesta *(recomendado)*

B) Trabajar directamente con `DiscoveryObservation` de foundation desde el scanner (sin capa intermedia)

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 12 — Frontera de reconciliación con U2 (ST-M2-03/04)

Contexto: `unit-of-work.md` §U4: "la reconciliación histórica pertenece a U2 (InventoryService)"; U2 ya emite `asset_first_seen`/`asset_missing` con umbral `SENTINEL_MISSING_CYCLES`.

A) U4 **solo produce y envía observaciones**; `first_seen`/`missing`/eventos E-01/E-02 los decide U2 tal como fue aprobado — sin lógica de inventario en U4 *(recomendado)*

B) U4 calcula el diff de inventario y envía eventos explícitos al Core (duplicaría y entraría en conflicto con U2)

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 13 — `sensor_id` (ST-M1-03 documented-only, FR-DISC-04)

Contexto: `unit-of-work.md` marca ST-M1-03 como **documented-only**; el modelo U1 ya tiene `sensor_id` con default `sensor-0`; el AC habla de `sensor.id=sensor-01` vía values (llegaría en U9).

A) Usar el default `sensor-0` de `DiscoveryObservation` (U1); sin clave nueva; el soporte de `sensor.id` configurable queda documentado para U9 *(recomendado; respeta el alcance documented-only)*

B) Implementar ya `SENTINEL_DISCOVERY_SENSOR_ID` (default `sensor-0`) en el loader de U4 (más cerca del AC, pero construye historia marcada documented-only)

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 14 — SNMP y cambio de puerto/servicio (ST-M1-04, ST-M2-05 documented-only)

Contexto: ambas marcadas **documented-only** en `unit-of-work.md`; `EventType.PORT_SERVICE_CHANGED` existe en foundation pero U2 no lo emite hoy; FR-DISC-05 define SNMP v2c/v3 con OIDs.

A) **Solo documentadas en el FD** (secciones de extensión): SNMP como módulo opcional futuro (OIDs/credenciales v2c/v3 vía Helm) y `PortServiceChanged` como responsabilidad futura de la reconciliación de U2 — **sin código en U4** *(recomendado)*

B) Implementar un stub de SNMP deshabilitado por defecto (`snmp.enabled=false`) en U4

C) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 15 — Estructura de paquete y wiring del runner (GT-02, unit-of-work §imports)

Contexto: el Dockerfile documenta `python -m sentinel.discovery`; GT-02 exige que `POST /api/v1/discovery` (GUI) funcione en la imagen estándar ⇒ `create_app` necesita un runner por defecto; la regla de frontera dice que **los colectores solo importan `foundation`** (dirección collector→core prohibida; la inversa core→collector es composición de arranque).

A) `src/sentinel/discovery/` con `__main__.py` (CLI), `config.py`, `scope.py` (C12), `scanner.py`, `domain.py`, `worker.py`, `client.py`; y `create_app` importa **perezosamente** `discovery.runner` como runner por defecto (inyección `runner=` para tests) ⇒ GT-02 funciona con la imagen estándar; dirección core→discovery documentada como composición de arranque *(recomendado)*

B) Mismos módulos, pero el runner solo se inyecta desde un entrypoint nuevo (CMD distinto) — la imagen U1 no arranca GT-02 sin cambiar su CMD

C) El worker vive dentro de `core/discovery/` (rompe "colectores solo importan foundation")

D) Other (describe después de `[Answer]:`)

[Answer]: A

### Question 16 — Semántica de `hosts_seen` (contrato `CycleRunner -> int`)

Contexto: `DiscoveryTrigger` persiste `hosts_seen` en `discovery_runs` y lo expone en `GET /discovery/{run_id}`; U2 solo lo consume como entero no negativo.

A) **Hosts con ≥1 hallazgo reportado** en el ciclo (respuesta ARP/ICMP/TCP o puerto abierto) *(recomendado)*

B) Hosts **intentados** (targets dentro de la allowlist que el ciclo trató de sondear, respondan o no)

C) Other (describe después de `[Answer]:`)

[Answer]: A

---

## 4. Follow-up (Step 5 — ambigüedad detectada)

> Responde FQ1 reemplazando el espacio después de `[Answer]:` por la letra elegida (o responde `Acepto todo`).

### FQ1 — Reporte de fallos del ciclo standalone hacia el Core (interacción Q4 × Q8)

Contexto: Q4=A compromete al CronJob de U9 a correr `python -m sentinel.discovery --once` como Job independiente (services.md §2.1: `CronJob → worker → POST /ingest`), pero Q8=A pone el log `DiscoveryCycleFailed` y el contador `sentinel_discovery_cycles_failed_total` **en el Core**, que solo conoce los runs creados por `POST /api/v1/discovery`. Un fallo del Job programado (scope violation, crash de nmap, timeout) no tiene hoy canal para llegar al `/metrics` de Core. ST-M2-06 exige log **y** contador para "un Job de descubrimiento que falla".

A) **Endpoint acotado de reporte**: `POST /api/v1/discovery/report` (body: `status: failed|timeout`, `cause`, `hosts_seen` opcional; Bearer token) ⇒ el Core incrementa `sentinel_discovery_cycles_failed_total` y emite `event=discovery_cycle_failed`; si el Core no responde ⇒ log local del Job (`kubectl logs`) como mejor esfuerzo. Mantiene Q4 (`--once`) y services.md §2.1 intactos; es una edición acotada más de U2 (junto a Q1 y Q7) *(recomendado)*

B) **CronJob dispara vía API**: el Job de U9 hace `POST /api/v1/discovery` (como la GUI) ⇒ validación, lock único, timeout, log y métrica viven todos en Core sin endpoint nuevo; `--once` queda para tests/demo. Desvía services.md §2.1 (el flujo programado dejaría de ser worker→ingest directo) y comparte el lock 409 con los triggers manuales

C) **Sin reporte**: los fallos standalone solo quedan en los logs del Job; `failed_total` cuenta únicamente los runs vía API (el AC de ST-M2-06 se verifica con un fallo manual). Cumplimiento parcial de la historia para el flujo CronJob

D) Other (describe después de `[Answer]:`)

[Answer]: C
