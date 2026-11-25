# Infrastructure Design — U3 (Operator GUI & network report)

**Fase**: CONSTRUCTION — Infrastructure Design (Parte 2: Generation)
**Fecha**: 2026-11-14
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U3 — `src/sentinel/gui/` (Runtime: imagen + Pod compartido con el Core)
**Decisiones (plan Q1–Q8)**: **A en todas** — Dockerfile ampliado en Code Gen U3 (libs WeasyPrint); resources sin cambios (validar pico PDF en U11); reportes efímeros sin PVC; sin flag de habilitación; puertos/Services/probes intactos; templates+static baked en imagen; sin límite de concurrencia de renders.
**Entradas**: FD, NFR Requirements y NFR Design de U3 (aprobados), infra de U2 (ID-U2-01..09), TS-U3-01..11, `requirements.md` §4.

---

## 1. Mapeo componente lógico → infraestructura real

| Componente lógico (NFR Design) | Infraestructura real | Notas |
|---|---|---|
| Router `/ui/*` + viewmodels (`gui/routes.py`) | **Mismo proceso uvicorn** dentro del Pod `sentinel-core` (bloque en `create_app`, NFR Design Q10) | Sin contenedor ni Service nuevos |
| `GuiClient` (loopback 8080) | Tráfico **interno al Pod**: `127.0.0.1:8080` (`API_BASE`, TS-U3-09) | No sale del contenedor; sin NetworkPolicy nueva |
| `gui/templates/*.html` + `gui/static/` | **Baked en la imagen** (`COPY` en el Dockerfile, TECH-03) | Sin ConfigMap, sin volumen (Q7=A) |
| `gui/report/{service,sections,pdf}.py` | **En memoria**, servido en 8080; nada en disco (Q3=A) | WeasyPrint usa CPU/RAM del propio Pod durante el render |
| Libs WeasyPrint (pango/cairo/gdk-pixbuf/fontconfig/ttf-dejavu) | **`apk add` en el Dockerfile heredado** (Q1=A; edición acotada ya declarada en TS-U3 §3) | Imagen única; crecimiento de tamaño sin cambio de base |
| Probes, resources, Service, PVC, Secret, ServiceMonitor | **Idénticos a U2** (ID-U2-02..05) | Q2/Q5/Q6=A: cero cambios de manifiesto |
| Habilitación de la GUI | **Sin flag** (Q4=A): siempre presente si el módulo importa | `try/except ImportError` = degradación defensiva, no feature flag |

**No aplican a U3** (con justificación): Messaging (sin broker); ConfigMap de templates (baked, Q7=A); PVC/almacenamiento de reportes (efímeros, Q3=A); Service/Service/puertos nuevos (comparte 8080, Q5=A); probes propios (hereda U2, Q6=A); namespace nuevo (hereda `sentinel` de U2); `shared-infrastructure.md` (sin infra compartida multi-unidad nueva).

---

## 2. Decisiones y justificación

| # | Decisión | Por qué |
|---|---|---|
| ID-U3-01 | Ampliar el Dockerfile de U1/U2 en Code Gen U3: `apk add --no-cache pango cairo gdk-pixbuf fontconfig ttf-dejavu` + `pip install jinja2 markdown weasyprint` | TECH-02/FQ1 exigen WeasyPrint; la edición ya está declarada como impacto heredado (TS-U3 §3); multi-stage y postergar a U9 romperían Build & Test (Q1=A) |
| ID-U3-02 | Resources del Pod **sin cambios** (100m/128Mi → 500m/512Mi) | Render breve y acotado (≤50 activos, timeout 30 s); pico a validar en U11, subir solo si la demo lo justifica (Q2=A) |
| ID-U3-03 | Reportes **efímeros** (en memoria, sin disco) | El operador los descarga; no hay requisito de retención (NFR/AVAIL); el PVC queda solo para evidencia SQLite (Q3=A) |
| ID-U3-04 | **Sin flag** de habilitación (sin env, sin `values.ui`) | La imagen del proyecto siempre incluye la GUI; TS-U3-07 fija cero claves nuevas (Q4=A) |
| ID-U3-05 | **Sin puertos ni Services nuevos**: `/ui` y `/static` en 8080 | Mismo proceso/puerto; separar no aisla nada en un solo Pod (Q5=A) |
| ID-U3-06 | **Probes intactos** (TCP 8080 + readiness `/api/v1/health`) | La fuente de datos de la GUI es el Core; readiness sobre `/ui/health` acoplaría el Pod a un módulo opcional (Q6=A) |
| ID-U3-07 | Templates + static **baked** en la imagen | Una pieza versionada con el código; hot-reload de ConfigMap desincroniza plantillas y código (Q7=A) |
| ID-U3-08 | **Sin límite de concurrencia** de renders PDF | Timeout 30 s + envolvente acotan el pico dentro del limit de 512Mi; semáforo añadiría estado y 503 innecesarios (Q8=A) |
| ID-U3-09 | Manifestos K8s **sin cambios** respecto a U2; U9 no recibe claves nuevas por U3 | U3 no añade objetos ni variables (Q5/Q6/Q7); los valores de U2 (ID-U2-09) siguen siendo los del chart |

---

## 3. Especificación de cambios de imagen (único artefacto construido en U3)

### 3.1 Dockerfile (edición acotada, heredado de U1 — Q1=A)

```dockerfile
# … bloques existentes de U1/U2 intactos …
RUN apk add --no-cache \
      pango cairo gdk-pixbuf fontconfig ttf-dejavu
RUN pip install --no-cache-dir \
      jinja2==<pin> markdown==<pin> weasyprint==<pin>   # pines exactos en requirements.txt / TS-U3-02
# … COPY de src/ + gui/static/ + gui/templates/ …
```

- Los pines exactos de `jinja2`, `markdown` y `weasyprint` se fijan en Code Gen (§2 de `tech-stack-decisions.md`).
- `COPY` adicional de `src/sentinel/gui/static/` y `src/sentinel/gui/templates/` (ya cubiertos si el `COPY src/` es recursivo — verificar en Code Gen).

### 3.2 Manifiestos K8s — sin cambios (referencia a U2)

| Manifiesto | Estado | Detalle |
|---|---|---|
| Deployment `sentinel-core` | **Idéntico** (ID-U2-01) | Mismo container, env, resources, probes, volumen |
| Service `sentinel-core` | **Idéntico** (ID-U2-04) | `http-api:8080` ahora sirve `/ui/*` y `/static/*` además de `/api/v1/*` |
| PVC / Secret / ServiceMonitor | **Idénticos** (ID-U2-03/05/07) | Nada que añadir |

---

## 4. Entradas para `values.yaml` de U9 — sin entradas nuevas por U3

| Clave propuesta por U3 | Valor | Nota |
|---|---|---|
| — | — | **U3 no añade claves** (Q4/Q7=A): no `ui.enabled`, no `ui.resources`, no `report.*`; la GUI viaja dentro de `core.image` |
| `core.image` (hereda U2) | `sentinel:test` | La imagen ya contiene la GUI (ID-U3-01); documentar en el chart que la imagen sirve `/ui` |

OQ-03 (values) no cambia por U3: las únicas "entradas" de U3 son las del Dockerfile (§3.1), que viven en el repo, no en el chart.

---

## 5. Recursos consumidos por U3

| Recurso | Propiedad | Coste/mantenimiento |
|---|---|---|
| CPU/RAM del Pod existente | Compartida con el Core (mismo contenedor) | Render PDF puntual; sin objeto nuevo en kind |
| Tamaño de imagen | +`apk` libs y 3 wheels de pip (crecimiento de la cap) | Build local algo más lento; sin efecto en runtime |
| Disco | **Cero** (reportes efímeros, sin ConfigMap/volumen) | Nada que purgar ni retener |
| Red | Cero: loopback interno + 8080 existente | Sin puertos ni policies nuevas |

---

## 6. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
