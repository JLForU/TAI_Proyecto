# Infrastructure Design Plan — U4 (Configuration, scope & Discovery)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 1: Planning)
**Fecha**: 2026-11-16
**Estado**: ARTIFACTS_GENERATED — Q1–Q7 todas A (2026-11-16); artefactos generados; pendiente de aprobación
**Unidad**: U4 — `src/sentinel/discovery/` (Runtime: proceso worker — CronJob en U9 o `--loop` local)
**Entradas**: Functional Design, NFR Requirements y NFR Design de U4 (aprobados), `requirements.md` §4 (K8s 1.28+, kind, Alpine), NFR-U4-TECH-01..04, TS-U4-01..12, infra de U2 (`infrastructure-design.md`: Deployment/Service/PVC/Secret/ServiceMonitor en namespace `sentinel`), FQ1=C (sin reporte/ métrica de fallos), nota de despliegue del usuario ("Todo el Proyecto se va a desplegar en mi máquina").

---

## 1. Contexto del assessment (Step 1 — analizado)

U4 **no despliega recursos propios**: el worker es un proceso aparte del Core (distinto contenedor/Job), pero **el chart lo construye U9**. Aquí se deciden los **impactos en la imagen** (binario `nmap`), la **forma del workload** (CronJob vs loop), **resources/SecurityContext**, el **requisito de egress** para escanear la LAN, la **observabilidad** del worker y la **entrega de configuración**. Los valores resultantes alimentan a U9/U10 igual que los de U2/U3.

Ya decidido (NO se pregunta): namespace `sentinel` y Service `sentinel-core:8080` heredados de U2; worker **stateless** (AVAIL-02, sin PVC); ingesta por **HTTP síncrono** con Bearer (decisiones de diseño #7 de U1, sin broker); sin endpoint ni ServiceMonitor propios del worker (FQ1=C + TS-U4-01); `SENTINEL_INGEST_TOKEN` desde el Secret heredado; loader estricto por env (TS-U4-03); usuario non-root (NFR-U4-SEC-02); K8s 1.28+/kind en la máquina del usuario; ServiceMonitor/PVC/entrypoint de U2 intactos.

**Categorías evaluadas**:

| Categoría | Aplica a U4 | Tratamiento |
|---|---|---|
| Deployment Environment | Sí | Q1 (Dockerfile +nmap), Q2 (forma del workload CronJob) |
| Compute Infrastructure | Sí | Q3 (resources del Job), Q4 (SecurityContext/caps) |
| Storage Infrastructure | No | **Sin pregunta**: worker efímero sin estado (AVAIL-02), sin caché ni archivos de salida — todo vive en la API Core (ya con PVC) |
| Messaging Infrastructure | No | **Sin pregunta**: sin broker — el worker llama a `POST /api/v1/ingest` de forma síncrona con `with_retries` (decisión de diseño #7 de U1; TS-U4-05) |
| Networking Infrastructure | Sí | Q5 (egress del worker: core:8080 + targets de la allowlist) |
| Monitoring Infrastructure | Sí | Q6 (observabilidad del worker: logs + heartbeat por observaciones) |
| Shared Infrastructure | Sí | Q7 (entrega de config: env desde values.yaml, sin ConfigMap); namespace/SA heredan de U2 (**sin pregunta**) |

---

## 2. Checklist del plan

- [x] Analizar Functional, NFR Requirements y NFR Design
- [x] Generar preguntas de infraestructura (Q1–Q7)
- [x] Recoger respuestas a los `[Answer]:`
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `infrastructure-design/infrastructure-design.md`
- [x] Generar `infrastructure-design/deployment-architecture.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de infraestructura

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Impacto en el Dockerfile (binario nmap) (Deployment Environment)

Contexto: TS-U4-02/Tech-stack §3 recomienda `apk add --no-cache nmap` en la imagen (la imagen de U1 no lo trae); D-U4-05 contempla el fallback a fixtures si falta nmap, pero **Build & Test de U4 y la demo reales** usan escaneo real.

A) **Edición acotada del Dockerfile en Code Gen U4**: `apk add --no-cache nmap` (busybox ya aporta `ping`/`ip`) + imagen única, sin etapa extra; si la edición se omite, el fallback fixtures cubre los tests *(recomendado)*

B) Multi-stage: etapa con nmap y copia selectiva del binario (imagen más ligera, copia de binario con dependencias frágil)

C) Postergar el Dockerfile a U9 (la imagen no tendría escaneo real hasta el chart; Build & Test de U4 correría con fixtures)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 2 — Forma del workload (Deployment Environment / Compute)

Contexto: FD Q4=A fija CLI `--once` (para CronJob en U9) y `--loop` (demo local sin chart); FR-DISC-03/ST-M1-01 piden descubrimiento periódico; el chart es de U9 pero la **forma esperada** se decide aquí.

A) **CronJob `--once` en U9**: `schedule: "*/15 * * * *"`, `concurrencyPolicy: Forbid`, `activeDeadlineSeconds` > timeout máximo de ciclo (p. ej. 600), `backoffLimit` bajo (p. ej. 3), `restartPolicy: Never`; `--loop` queda como modo de demo local sin chart *(recomendado)*

B) Deployment con `--loop` (repliquas permanentes; más difícil de operar, no coincide con las stories "CronJob/Job")

C) Job manual solamente (sin periodicidad — rompe FR-DISC-03)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 3 — Resources del worker (Compute Infrastructure)

Contexto: U2 fija `requests: 100m/128Mi · limits: 500m/512Mi` para el Core; el worker corre `nmap`/`ping` acotados por presupuesto de fases (20/30/30/20 s) y cap 1000 targets (P13).

A) **Mismos resources que el Core** (100m/128Mi → 500m/512Mi): el ciclo es breve y acotado por deadline; validar el pico real de nmap en U11 durante la demo y subir solo si hace falta *(recomendado)*

B) Subir preventivamente a `limits: 1 CPU/1Gi` para dar margen a nmap en /24

C) Sin resources explícitos (default del namespace)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 4 — SecurityContext y capabilities (Compute / Security)

Contexto: NFR-U4-SEC-03 pide **non-root sin capabilities**; el socket ICMP de `ping` puede fallar en containers sin `NET_RAW`/`ping_group_range` (D-U4-05 degrada la fase ICMP a "omitida"; ARP/TCP siguen cubriendo el descubrimiento). NFR-U4-SEC-02 admite "except sensor capabilities".

A) **Sin capabilities** (como SEC-03): si el kernel no permite ICMP a non-root, la fase ICMP se omite con warning y el descubrimiento sigue por ARP/TCP/nmap; consistente con la seguridad por defecto *(recomendado)*

B) Conceder `NET_RAW` **solo al SecurityContext del CronJob/worker` (no al Core) para ICMP fiable — desvío documentado de SEC-03 amparado por la excepción de sensor de SEC-02

C) Ejecutar el worker como root (rompe SEC-02)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 5 — Egress del worker (Networking Infrastructure)

Contexto: U10 prevé NetworkPolicies con default-deny; el worker necesita: **(a)** DNS, **(b)** `sentinel-core:8080` (ingest), **(c)** tráfico saliente hacia los **targets de la allowlist** (LAN real). Si el default-deny lo aplasta, el escaneo falla en silencio (todo `failed`).

A) **Documentar en este diseño el requisito de egress** (política del worker permite DNS + `sentinel-core:8080` + rango/CIDR de `scope.*` tomado de `values.yaml`); la política concreta se implementa en **U9/U10** *(recomendado)*

B) Worker **sin NetworkPolicy** (todo egress abierto — más simple, menos seguro, contradice SEC-01)

C) `hostNetwork: true` del worker (acceso directo a la LAN, complica el aislamiento y expone puertos del host)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 6 — Observabilidad del worker (Monitoring Infrastructure)

Contexto: FQ1=C rechaza reporte de fallos y métricas nuevas; el Core no ve los ciclos del CronJob (no hay POST en fallo); los ciclos **exitosos** sí actualizan el sensor_heartbeat (`sensor-0`) y `last_discovery_run` vía `/discovery` solo aplica a invocaciones manuales. El operador necesita distinguir "sensor caído" vs "red sin activos" (ST-M2-06).

A) **Solo logs JSON a stdout** (`kubectl logs` del Job + modo `--loop`), vitalidad del worker reflejada por las **observaciones exitosas** (heartbeat `sensor-0`) y por `kubectl get jobs`; sin canal ni métrica nuevos — consistente con FQ1=C *(recomendado)*

B) Heartbeat ligero al Core **incluso en ciclo fallido** (evento/observación sintética — reintroduce el canal de reporte que FQ1=C rechazó)

C) Lease/ConfigMap de K8s para "colectores vivos" (K8s-native, pieza nueva en U9, no la ve el dashboard)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 7 — Entrega de configuración (Shared Infrastructure)

Contexto: el worker lee `SENTINEL_DISCOVERY_*` por env estricto (TS-U4-03, D-U4-03); U9 mapea `values.yaml` → env del CronJob; el único secreto es `SENTINEL_INGEST_TOKEN` (Secret heredado). No hay ConfigMap de U2.

A) **Todo por env**: U9 traduce `discovery.*` de `values.yaml` a variables `SENTINEL_DISCOVERY_*` en el contenedor del CronJob (y `SENTINEL_INGEST_TOKEN` desde el Secret existente); **sin ConfigMap nueva** *(recomendado)*

B) ConfigMap para `scope.*`/`interval` montada como env (más K8s-nativo, pero añade una pieza que el loader estricto no pide y U2 no usa)

C) Otro (describe después de `[Answer]:`)

[Answer]: A
