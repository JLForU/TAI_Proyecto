# Infrastructure Design Plan — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 1: Planning)
**Fecha**: 2026-11-14
**Estado**: ARTIFACTS_GENERATED — Q1–Q8 todas A (2026-11-14); artefactos generados; pendiente de aprobación
**Unidad**: U3 — `src/sentinel/gui/` (Runtime: imagen + Pod compartido con el Core)
**Entradas**: Functional Design, NFR Requirements y NFR Design de U3 (aprobados), `requirements.md` §4 (K8s 1.28+, kind, Alpine), NFR-U3-TECH-01..03 (static baked, WeasyPrint), TS-U3-01..11, infra de U2 (`infrastructure-design.md`: Deployment/Service/PVC/Secret/ServiceMonitor en namespace `sentinel`), nota de despliegue del usuario ("Todo el Proyecto se va a desplegar en mi máquina").

---

## 1. Contexto del assessment (Step 1 — analizado)

U3 **no despliega recursos nuevos**: la GUI corre en el **mismo proceso/Pod/Contenedor** que el Core (NFR Design Q10=A: bloque en `create_app`). Aquí se deciden los **impactos en la imagen** (libs de WeasyPrint), los **recursos del Pod** con render PDF, la **persistencia (o no) de reportes**, la **habilitación** de la GUI y si los probes/services de U2 cambian. Los valores resultantes alimentan a U9 (chart) igual que los de U2.

Ya decidido (NO se pregunta): single container/Pod con el Core (NFR Design Q10); comparte el Service `sentinel-core:8080` (TS-U3-09); sin claves de config nuevas (TS-U3-07); static vendorizado baked en imagen (TECH-03); acceso solo port-forward (NFR-U3-SEC-03); namespace `sentinel` (U2 Q8); ServiceMonitor/PVC/Secret/entrypoint de U2 intactos; sin sesión/cookies.

**Categorías evaluadas**:

| Categoría | Aplica a U3 | Tratamiento |
|---|---|---|
| Deployment Environment | Sí | Q1 (Dockerfile/libs WeasyPrint), Q4 (habilitación de la GUI) |
| Compute Infrastructure | Sí | Q2 (resources del Pod con PDF), Q8 (concurrencia de renders) |
| Storage Infrastructure | Sí | Q3 (persistencia de reportes) |
| Messaging Infrastructure | No | **Sin pregunta**: sin broker (decisión de diseño #7 de U1) |
| Networking Infrastructure | Sí | Q5 (puertos/Services: sin cambios) |
| Monitoring Infrastructure | Sí | Q6 (probes: sin cambios) |
| Shared Infrastructure | Sí | Q7 (sin ConfigMap; templates baked) · namespace hereda de U2 (**sin pregunta**) |

---

## 2. Checklist del plan

- [x] Analizar Functional, NFR Requirements y NFR Design
- [x] Generar preguntas de infraestructura (Q1–Q8)
- [x] Recoger respuestas a los `[Answer]:` (todas A, 2026-11-14)
- [x] Analizar respuestas y resolver ambigüedades — todas A/recomendadas; sin ambigüedades; sin seguimientos
- [x] Generar `infrastructure-design/infrastructure-design.md`
- [x] Generar `infrastructure-design/deployment-architecture.md`
- [x] Presentar mensaje de completitud y esperar aprobación

---

## 3. Preguntas de infraestructura

> Responde cada pregunta reemplazando el espacio después de `[Answer]:` por la letra elegida. Si aceptas todas las recomendaciones, escribe `A` en todas (o responde `Acepto todo`).

### Question 1 — Impacto en el Dockerfile (libs de WeasyPrint) (Deployment Environment)

Contexto: TECH-02/FQ1=A fija WeasyPrint; en Alpine las libs (`pango`, `cairo`, `gdk-pixbuf`, `fontconfig`, `ttf-dejavu`) no vienen en la imagen base de U1; TS-U3 §3 ya declara esta edición heredada.

A) **Edición acotada del Dockerfile en Code Gen U3**: `apk add --no-cache pango cairo gdk-pixbuf fontconfig ttf-dejavu` + `pip install` de los 3 paquetes nuevos (jinja2, markdown, weasyprint); imagen única, sin etapa extra *(recomendado)*

B) Multi-stage build: etapa de build con las libs y copia selectiva de `.so` (imagen más ligera, copia frágil y difícil de mantener)

C) Postergar el Dockerfile a U9 (la imagen de U1 no tendría GUI hasta el chart — rompe Build & Test de U3)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 2 — Resources del Pod con render PDF (Compute Infrastructure)

Contexto: U2 fija `requests: 100m/128Mi · limits: 500m/512Mi`; WeasyPrint consume memoria durante el render (lab ≤50 activos, PDF de pocas páginas, timeout 30 s — PERF-02).

A) **Mantener los resources de U2** (100m/128Mi → 500m/512Mi): el render es breve y acotado (≤50 activos, 1 PDF a la vez por el timeout); validar el pico real en U11 durante la demo y subir solo si hace falta *(recomendado)*

B) Subir preventivamente a `limits: 768m/1Gi` para dar margen al PDF (más holgura, Pod más pesado en kind)

C) Resources diferenciados no aplican (un solo contenedor); sin cambios y sin validación en U11

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 3 — Persistencia de reportes (Storage Infrastructure)

Contexto: el reporte se genera bajo demanda (FD: `POST/GET /ui/report`); el PVC de U2 (`/data`) guarda solo la evidencia SQLite; AVAIL-01 no pide retención de reportes.

A) **Efímero**: MD/PDF se construyen en memoria y se sirven con `FileResponse`/`Response`; **nada en disco**, sin PVC nueva, sin directorio de salidas; el operador descarga si quiere conservarlo *(recomendado)*

B) Guardar las últimas N copias en `/data/reports/` (útil para re-descarga, mezcla reportes con evidencia en el PVC)

C) Directorio temporal del sistema (`/tmp`) con purga (más piezas, sin beneficio sobre la memoria)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 4 — Habilitación de la GUI (Deployment Environment / Shared)

Contexto: NFR Design Q10=A deja el montaje como bloque try/except (sin `gui` ⇒ solo-API); no hay claves nuevas (TS-U3-07); U9 podría querer apagar la GUI desde `values.yaml`.

A) **Sin flag**: la GUI está siempre presente en la imagen del proyecto y se monta automáticamente; el try/except es solo degradación defensiva ante import roto; cero env, cero entrada en `values.yaml` *(recomendado)*

B) Variable `SENTINEL_UI_ENABLED` (default `true`) + entrada `ui.enabled` en `values.yaml` de U9 (control desde K8s, añade config que TS-U3-07 dice que no existe)

C) Flag solo en `values.yaml` sin env (control parcial, la imagen siempre la trae)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 5 — Puertos y Services (Networking Infrastructure)

Contexto: API y GUI comparten proceso (NFR Design Q10); U2 define un Service `sentinel-core` con `http-api:8080` y `http-metrics:9108`.

A) **Sin cambios**: `/ui/*` y `/static/*` se sirven en **8080** (mismo puerto que la API); cero puertos nuevos, cero Services nuevos, cero probes de red nuevos; port-forward existente cubre GUI y API *(recomendado)*

B) Service adicional `sentinel-ui` (ClusterIP 8080→8080) separando tráfico (duplica superficie sin aislar nada: mismo Pod/puerto)

C) Segundo contenedor en el Pod sirviendo estáticos (nginx sidecar — dos imágenes, sincronización de archivos, sin ventaja en lab)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 6 — Probes del Pod (Monitoring Infrastructure)

Contexto: U2 fija liveness TCP 8080 · readiness `GET /api/v1/health` · startupProbe TCP; la GUI no tiene estado propio (AVAIL-02).

A) **Sin cambios**: mantener los probes de U2 — la GUI comparte proceso y la readiness ya valida el Core (la que es, en última instancia, la fuente de datos de la GUI) *(recomendado)*

B) Cambiar readiness a `GET /ui/health` (detectaría además un montaje `/ui` roto, pero acopla el readiness del Pod a un módulo "opcional" y a la API loopback en cadena)

C) Tercer probe específico para `/static` (ruido: un fichero ausente no debe reiniciar el Pod)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 7 — Templates y static: imagen vs ConfigMap (Shared Infrastructure)

Contexto: TECH-03 fija static vendorizado en repo; los templates van en `gui/templates/`; hot-reload de templates sería el único valor de un ConfigMap.

A) **Todo baked en la imagen** (Dockerfile `COPY` de `gui/static/` y `gui/templates/`): una pieza, versionada con el código, sin volúmenes; cambiar templates ⇒ redeploy (aceptable en lab) *(recomendado)*

B) ConfigMap con los templates montado en el Pod (edits sin redeploy, pero desincroniza código y plantillas, añade manifiesto y volumen)

C) ConfigMap solo para `tailwind.css` build-time (mezcla artefactos de build con runtime)

D) Other (describe después de `[Answer]:`)

[Answer]: A
### Question 8 — Concurrencia de renders PDF (Compute / Reliability)

Contexto: dos operadores podrían pedir PDF a la vez (lab raro pero posible); cada render consume memoria (Q2); timeout global 30 s (PERF-02).

A) **Sin límite de concurrencia**: el timeout de 30 s y la envolvente ≤50 activos acotan el pico; si hay doble render, el Pod usa más memoria del request pero dentro del limit de 512Mi — validar en U11 *(recomendado)*

B) Semáforo en la app: **máx. 1 render concurrente**; si está ocupado ⇒ 503 "reporte en curso" (controla memoria, añade estado y posible rechazo)

C) Cola de reportes con reintento automático (más piezas, nadie la pidió)

D) Other (describe después de `[Answer]:`)

[Answer]: A
---

## 4. Artefactos obligatorios (tras aprobación)

| Artefacto | Contenido |
|---|---|
| `construction/u3-gui/infrastructure-design/infrastructure-design.md` | Impacto de U3 en la infraestructura existente: cambios de imagen (Dockerfile), recursos (sin nuevos), reportes efímeros, probes/services intactos, entradas/absencia de entradas para `values.yaml` de U9 |
| `construction/u3-gui/infrastructure-design/deployment-architecture.md` | Topología actualizada (GUI en el mismo Pod), flujo port-forward → `/ui`, flujo de generación de reporte, ciclo dev/demo con la GUI |

> `shared-infrastructure.md` **no** aplica: U3 no añade infraestructura compartida (namespace y secrets heredan de U2; consolidados en U9).

---

## 5. Gate de aprobación

1. Completa todos los `[Answer]:`.
2. Responde `Listo` para que valide respuestas y ambigüedades.
3. Si hay ambigüedades, añadiré preguntas de seguimiento.
4. Si no las hay, generaré los dos artefactos de Infrastructure Design y presentaré el mensaje de completitud.

**No se genera ningún artefacto de Infrastructure Design hasta completar este gate.**
