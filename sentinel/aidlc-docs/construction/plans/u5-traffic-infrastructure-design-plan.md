# Infrastructure Design Plan — U5 (Traffic Sensor & ARP observation)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 1: Planning)
**Fecha**: 2026-11-19
**Estado**: GENERATED — respuestas todas A (2026-11-19); artefactos generados; pendiente de aprobación
**Unidad**: U5 — `src/sentinel/traffic/` (Runtime: proceso worker — Deployment `--loop` en U9 o `--once` local)
**Entradas**: Functional Design, NFR Requirements y NFR Design de U5 (aprobados 2026-11-18/19), `requirements.md` §4 (K8s 1.28+, kind, Alpine) y OQ-01 (a resolver aquí), NFR-U5-SEC-01/02, TS-U5-01..13, infra de U2 (`infrastructure-design.md`: Deployment/Service/PVC/Secret/ServiceMonitor en namespace `sentinel`), infra de U4 (worker sin Service/probe; requisito de egress documentado), nota de despliegue del usuario ("Todo el Proyecto se va a desplegar en mi máquina").

---

## 1. Contexto del assessment (Step 1 — analizado)

U5 **no despliega recursos propios**: el sensor es un proceso worker aparte del Core (distinto contenedor), pero **el chart lo construye U9**. Aquí se deciden los **impactos en la imagen** (sin cambios esperados), la **forma del workload** (Deployment `--loop` vs alternativas), **resources/SecurityContext** (incluida la **resolución de OQ-01**: ¿se puede descartar `CAP_SYS_ADMIN`?), el **requisito de egress** para exportar al Core, la **observabilidad** del sensor (sin `/metrics` propio) y la **entrega de configuración** `SENTINEL_TRAFFIC_*`. Los valores resultantes alimentan a U9/U10 igual que los de U2/U3/U4.

Ya decidido (NO se pregunta): namespace `sentinel` y Service `sentinel-core:8080` heredados de U2; sensor **stateless** (NFR-AVAIL-01, sin PVC); ingesta por **HTTP síncrono** con Bearer y `with_retries` ×5 (decisiones de diseño #7 de U1, sin broker); sin endpoint ni ServiceMonitor propios del sensor (NFR-U5-MNT-04 + TS-U5 sin `/metrics`); `SENTINEL_INGEST_TOKEN` desde el Secret heredado; loader estricto por env `SENTINEL_TRAFFIC_*` (TS-U5-05); imagen **non-root** sin capabilities en el MVP (NFR-U5-SEC-01); sin scapy ni sockets crudos en el paquete (BR-U5-33); K8s 1.28+/kind en la máquina del usuario; ServiceMonitor/PVC/entrypoint de U2 intactos; FD §5 ya fija `chart = Deployment --loop` con `traffic.window/interface/simRate`, `sensor.id` ⇒ env (NFR-OPS-01).

**Categorías evaluadas**:

| Categoría | Aplica a U5 | Tratamiento |
|---|---|---|
| Deployment Environment | Sí | Q1 (forma del workload), Q2 (impacto en el Dockerfile) |
| Compute Infrastructure | Sí | Q3 (resources del Pod), Q4 (**OQ-01** — `CAP_SYS_ADMIN` en el diseño documentado de captura) |
| Storage Infrastructure | No | **Sin pregunta**: sensor efímero sin estado (NFR-AVAIL-01), sin caché ni archivos — todo lo persiste Core (ya con PVC); ventana descartable ante fallo (D-U5-05) |
| Messaging Infrastructure | No | **Sin pregunta**: sin broker — `POST /api/v1/ingest` síncrono con retries (decisión de diseño #7 de U1; TS-U5-06) |
| Networking Infrastructure | Sí | Q5 (egress del sensor: DNS + Core; salvedad `hostNetwork` futuro) |
| Monitoring Infrastructure | Sí | Q6 (observabilidad: logs + heartbeat por observaciones; sin probe ni puerto) |
| Shared Infrastructure | Sí | Q7 (entrega de config: env desde values.yaml, sin ConfigMap); namespace/SA/Secret heredan de U2 (**sin pregunta**) |

---

## 2. Checklist del plan

- [x] Analizar Functional, NFR Requirements y NFR Design
- [x] Generar preguntas de infraestructura (Q1–Q7)
- [x] Recoger respuestas a los `[Answer]:` (2026-11-19: "Acepto todo lo recomendado" ⇒ Q1–Q7 = A)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; interacciones revisadas (Q1×Q5 (Deployment --loop sin hostNetwork en MVP), Q4×OQ-01 (descarte documentado), Q6×MNT-04 (sin /metrics propio)) ⇒ **sin FQ necesarias**
- [x] Generar `infrastructure-design/infrastructure-design.md`
- [x] Generar `infrastructure-design/deployment-architecture.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de infraestructura

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Forma del workload del sensor (Deployment Environment / Compute)

Contexto: FD §5 y NFR-OPS-01 ya apuntan a `chart = Deployment --loop` (`python -m sentinel.traffic --loop`); NFR-AVAIL-01 fija **un solo sensor** en el MVP; el sensor necesita ventanas continuas para heartbeat (`sensor_heartbeats`) y la demo GT-05 usa `--loop`.

A) **Deployment con `replicas: 1` y `--loop`** (reinicio por `restartPolicy: Always`; SIGTERM entre ventanas; heartbeat continuo vía observaciones; coherente con FD §5 y U4 usó CronJob porque su actividad es intermitente — la captura/observación no lo es) *(recomendado)*

B) **DaemonSet** (un Pod por nodo — prepararía captura por nodo futuro, pero excede el single-sensor del MVP y duplicaría observaciones/`sensor_id`)

C) **CronJob `--once`** por ventana (como U4; el worker viviría <1 s por tick — complicaría heartbeat continuo y `--loop` de la demo)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 2 — Impacto en el Dockerfile (Deployment Environment)

Contexto: TS-U5 (tech-stack §3) fija **`Dockerfile` sin cambios**: entrypoint `python -m sentinel.traffic` ya documentado (BR-26 U1), imagen Alpine non-root existente; el MVP no importa scapy (BR-U5-33) y las deps pip no cambian (TECH-01).

A) **Sin cambios en el Dockerfile** en Code Gen U5 (scapy/`AfPacketSource` llegarán —si se decide— con la captura real futura, fuera del alcance actual) *(recomendado)*

B) Pre-instalar `scapy` en la imagen ya (imagen lista para captura futura; peso y superficie innecesarios hoy, sin código que lo use)

C) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 3 — Resources del Pod sensor (Compute Infrastructure)

Contexto: U2 fija `requests: 100m/128Mi · limits: 500m/512Mi` para el Core; el sensor agrega en `dicts` O(1) por ventana (hot path ligero, P5) y hace POSTs locales con retries; el pico real (SIM_RATE alto en GT-04) se valida en U11.

A) **Mismos resources que el Core** (100m/128Mi → 500m/512Mi): trabajo acotado por ventana; validar el pico con SIM_RATE alto en U11 y subir solo si hace falta *(recomendado)*

B) Subir preventivamente a `limits: 1 CPU/1Gi` para margen con SIM_RATE alto

C) Sin resources explícitos (default del namespace)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 4 — OQ-01: `CAP_SYS_ADMIN` en el diseño documentado de captura (Compute / Security)

Contexto: `requirements.md` OQ-01 pregunta si `CAP_SYS_ADMIN` puede descartarse para `AF_PACKET`/`TPACKET_V3`; FR-TRAF-02 y FD §5 hoy documentan el Pod futuro con `hostNetwork` + `CAP_NET_RAW` + `CAP_NET_ADMIN` (+ `CAP_SYS_ADMIN` a evaluar); NFR-U5-SEC-01 exige resolver OQ-01 en NFR Design/Infra de U5. Técnico: abrir un socket `AF_PACKET` requiere `CAP_NET_RAW`; el modo promiscuo (`PACKET_ADD_MEMBERSHIP`/`SIOCGIFFLAGS`) requiere `CAP_NET_ADMIN`; `TPACKET_V3` en sí no exige `CAP_SYS_ADMIN`.

A) **Descartar `CAP_SYS_ADMIN`** del diseño documentado: el Pod futuro de captura queda con `hostNetwork: true` + `CAP_NET_RAW` + `CAP_NET_ADMIN` (solo si se usa modo promiscuo) — **OQ-01 resuelta: no se requiere**; se registra en este diseño y en requirements.md *(recomendado)*

B) Mantener `CAP_SYS_ADMIN` documentado "por si acaso" (superficie de privilegio máxima injustificada; contradice la minimización de SEC-01)

C) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 5 — Egress del sensor y salvedad `hostNetwork` (Networking Infrastructure)

Contexto: el sensor solo necesita **(a)** DNS y **(b)** `sentinel-core:8080` (ingest) — no escanea la LAN (eso es U4); U10 prevé NetworkPolicies con default-deny; `DECISIONES_PENDIENTES.md` §1 advierte que con `hostNetwork` el comportamiento de NetworkPolicy depende del CNI y puede no aplicar al Pod.

A) **Documentar en este diseño el requisito de egress** (política del sensor permite DNS + `sentinel-core:8080`; política concreta en **U9/U10**) **y la salvedad**: cuando el sensor pase a `hostNetwork` (captura real), la NetworkPolicy deja de ser el mecanismo de contención confiable — entonces el alcance se acota por configuración del CNI/bridge de laboratorio *(recomendado)*

B) Sensor **sin NetworkPolicy** (todo egress abierto — más simple, menos seguro)

C) `hostNetwork: true` **ya en el MVP** (innecesario con SimulatedSource; amplía privilegios sin justificación)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 6 — Probes y observabilidad del sensor (Monitoring Infrastructure)

Contexto: NFR-U5-MNT-04 prohíbe `/metrics` propio (los indicadores los publica U7 con las familias de U1); el sensor no expone puertos; la vitalidad se refleja en las **observaciones exitosas** (heartbeat `sensor-0` vía HealthService) y en los logs (`sensor_export_failed`, `window_clock_regression`, `arp_rate`); U4 adoptó "sin probe" por el mismo motivo (ID-U4-08).

A) **Sin puerto, sin probe ni Service propio**: logs JSON a stdout (`kubectl logs`), vitalidad vía heartbeat de observaciones y `kubectl get pods`; liveness lo aporta K8s ante crash/exit ≠ 0 (Deployment `--loop`) *(recomendado)*

B) `livenessProbe` por proceso/estado (p. ej. archivo o comando) — pieza nueva sin dónde apoyarse (el worker no escribe estado)

C) Exponer un puerto de salud + Service (añade superficie sin consumidor — Prometheus ya no scrapea al sensor)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 7 — Entrega de configuración (Shared Infrastructure)

Contexto: el sensor lee `SENTINEL_TRAFFIC_*` por env estricto (TS-U5-05: `window`, `interface`, `sim_rate`, `sensor_id`, `fallback`); U9 mapea `traffic.*`/`sensor.id` de `values.yaml` ⇒ env (NFR-OPS-01, FD §5); el único secreto es `SENTINEL_INGEST_TOKEN` (Secret heredado de U2); `helm lint --set traffic.window=7s` se valida detrás del loader (BR-U5-02) en U9/Build & Test.

A) **Todo por env**: U9 traduce `traffic.window/interface/simRate` y `sensor.id` de `values.yaml` a `SENTINEL_TRAFFIC_*` (y `SENTINEL_INGEST_TOKEN` desde el Secret existente); **sin ConfigMap nueva** *(recomendado)*

B) ConfigMap para `traffic.*` montada como env (más K8s-nativo, pero añade una pieza que el loader estricto no pide y U2/U4 no usan)

C) Other (describe después de `[Answer]:`)

[Answer]: A
---

## 4. Follow-up (Step 5 — ambigüedad detectada)

> Análisis de interacciones Q1×Q5 (Deployment `--loop` sin `hostNetwork` en MVP — la salvedad aplica a la captura futura), Q4×Q5 (`CAP_SYS_ADMIN` descartado; `NET_RAW`/`NET_ADMIN` documentados para U9), Q6×MNT-04 (sin puerto ni Service, sin `/metrics` propio): todas resueltas por A. **Sin follow-ups.**
