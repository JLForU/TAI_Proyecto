# Code Generation Summary — U5 (Traffic Sensor & ARP observation)

**Unidad**: U5 · **Fecha**: 2026-11-19 · **Plan**: `aidlc-docs/construction/plans/u5-traffic-code-generation-plan.md` (25/25 steps `[x]`, `Aprobado` 2026-11-19T03:10:00Z)
**Traza**: ST-M3-01..06 (todas documented-only) · FD §1.1/§3.1–3.6/BR-U5-01..36/D-U5-01..09 · NFR Req Q1–Q9/TS-U5-01..13 · NFR Design Q1–Q7/P1–P13 · Infra Q1–Q7/ID-U5-01..10 · Code Gen plan aprobado.

## 1. Archivos creados

| Área | Archivos |
|---|---|
| Paquete traffic | `src/sentinel/traffic/{__init__,config,source,aggregator,arp,client,worker,__main__}.py` (8) |
| Tests unitarios | `tests/unit/traffic/{__init__,test_config,test_source,test_minimal_fields,test_aggregation,test_arp,test_arp_rate,test_client,test_worker,test_cli,test_boundaries}.py` (11) + `tests/unit/traffic/fixtures/window_sample.json` |
| Tests integración | `tests/integration/test_traffic_export.py`, `tests/integration/test_arp_mapping_change.py` |
| PBT | `tests/property/test_window_aggregation.py` (3 propiedades hypothesis, MNT-03) |
| Docs | `aidlc-docs/construction/u5-traffic/code/code-generation-summary.md` (este archivo) |

## 2. Archivos modificados (ediciones acotadas)

| Archivo | Cambio | Verificación |
|---|---|---|
| `tests/integration/test_ingest_idempotency.py` | + `test_mixed_traffic_arp_batch_idempotent` (lote mixto traffic+arp ⇒ `accepted=0, deduplicated=2`, sin filas nuevas) | Step 20 / BR-U5-27 |
| `.github/workflows/ci.yml` (workspace root) | paso `Traffic coverage gate (U5, P11)` tras el de discovery: `coverage report --include='*/traffic/*' --fail-under=70` | gate local 95% ✓ (mantiene total/GUI/discovery) |
| `README.md` | sección **Traffic Sensor (U5)** (run `--once/--loop`, tabla `SENTINEL_TRAFFIC_*`, frontera sin scapy, heartbeat, ARP delegado en U2) + gate traffic en comandos de calidad | revisión manual |

**Cero ediciones a U1/U2/Dockerfile** (FD §4, ID-U5-02) — verificado: ningún archivo fuera de los listados fue tocado.

## 3. Desviaciones (D-*)

| ID | Desviación | Justificación |
|---|---|---|
| D-U5-10 | `SensorState.pending` en `worker.py`: el primer evento con `observed_at ≥ window_end` se conserva en memoria y se procesa al inicio de la siguiente ventana (en vez de descartarlo o releer la fuente) | BR-U5-25 exige cero pérdida en el borde; el evento en `t = window_end` pertenece a la ventana siguiente (semántica `[start, end)`); estado descartable por proceso (P1, sin buffer de export) |
| D-U5-11 | PBT de partición (PB-U5-01) verifica **disjunta + alineada + cobertura de paquetes** en vez de «sin huecos» absolutos entre primera y última ventana | Con paquetes dispersos (p. ej. dos paquetes separados un año) las ventanas intermedias **no existen** — exigir contigüad absoluta sería falso; el invariante real es: sin solapes, largo exacto `W`, alineación epoch y Σ paquetes conservados |
| D-U5-12 | `--once`/`--loop` duermen hasta el borde vía seam `_sleep_until_next_boundary` monkeypatcheable (no inyectado por constructor) | TS-U5-08/TECH-04: el CLI se prueba sin `sleep` real; seams por atributo de módulo siguen el patrón de `discovery/__main__.py` |

Además, la validación del Step 24 motivó autofix menores (orden de imports `I001`, formato `ruff format` en 3 archivos) — sin cambio de comportamiento.

## 4. Verificación de frontera (BR-U5-32/33)

- **Imports**: `ast` de `src/sentinel/traffic/*.py` ⇒ sin `sentinel.core.*` ni `sqlite3`; dentro de `sentinel` solo `foundation.*` + paquete propio (`test_boundaries.py`).
- **scapy/captura real**: `grep -ri scapy src/ requirements.txt` ⇒ **0**; sin `pypcap`. Captura AF_PACKET queda documented-only (FD §5, OQ-01 sin `CAP_SYS_ADMIN`).
- **Sin `/metrics` propio** (MNT-04), **sin deps nuevas** (TECH-01), **sin objetos K8s/Helm** (ID-U5-10, handoff a U9).

## 5. Validación local (Step 24 — todo verde)

```text
ruff check .                  → All checks passed!
ruff format --check .         → 168 files already formatted
mypy src/sentinel             → Success: no issues found (81 files)
pytest tests/unit tests/property tests/integration
  --cov=sentinel --cov-fail-under=70
  → 458 passed · total coverage 94.19% (gate ≥70 ✓)
coverage report --include='*/traffic/*' --fail-under=70
  → traffic 95% (371 stmts, 19 miss; gate ≥70 ✓)
coverage report --include='*/gui/*'      → 95% ✓   (regresión: sin cambios)
coverage report --include='*/discovery/*'→ 92% ✓   (regresión: sin cambios)
```

Tests U5: **63 nuevos** (unit traffic 55 + PBT 3 + integración 4 + idempotencia +1); 458 totales = 395 de U1–U4 sin regresiones. Cobertura por módulo: aggregator/arp 100%, source 99%, client 97%, config 95%, worker 92%, `__main__` 84%.

Nota: una ejecución aislada del suite completo sufrió un *segfault* intermitente del runtime (starlette/C-ext, no reproducible); 3 corridas subsiguientes (2 con cobertura) terminaron `exit=0` — se atribuye a contención ambiental, no al código de U5.

## 6. Historias y estado (documented-only)

ST-M3-01..06 permanecen **documented-only** en el story map (captura real AF_PACKET no demostrada — `implementation-scope.md` §3); el **simulador/fixtures es código de soporte de la unidad** (`unit-of-work.md` §U5). AC verificados con fuente simulada/fixtures + `MockTransport`/`TestClient` (D-U5-04 re-mapea rutas; `POST /ingest/traffic` documentado, se usa `/ingest` real):

| Historia | Verificación principal |
|---|---|
| ST-M3-01 Minimal metadata | `test_minimal_fields` (campos exactos + `no_payload`) |
| ST-M3-02 Ventanas configurables | `test_config` (`window_values`/`window_seven_rejected`) + `test_aggregation` (`epoch_aligned`, `five_second_windows`) + PBT |
| ST-M3-03 Export a Core | `test_client` (1 POST/ventana, chunking, sin `reconcile`) + `test_traffic_export` (consultable + `deduplicated`) + idempotencia mixta |
| ST-M3-04 ARP IP↔MAC | `test_arp` + `test_arp_mapping_change` (`arp_mapping_changed` en U2, `no_asset_created`) |
| ST-M3-05 ARP rate | `test_arp_rate` (`ten_per_second`, log `arp_rate` con `arp_messages_per_second`) |
| ST-M3-06 Mapping changed alert | `test_arp_mapping_change -k event` (sin atribución de ataque en `details`) |

## 7. Estado del repo (anomalía conocida)

- `sentinel/` **no tiene `.git`** (los commits del parent viven en `/home/jhoseph/Documents/TAI/TAI_Proyecto`); el parent tiene un gitlink roto `sentinel` (1 entrada en `ls-files`) y `.github/` aparece como `??` sin trackear.
- **Ningún commit de U1–U5** — todo el código y `aidlc-docs/` están sin versionar (consistente con U1–U4). No se hizo `commit` (requiere solicitud explícita).

## 8. Handoff (siguiente etapa)

- **Build and Test** (etapa F7): `helm template`/demo kind con GT-04/GT-05, gate total de imagen; **U9** consume el handoff de `deployment-architecture.md` §5 (Deployment `--loop`, NetworkPolicy egress DNS+8080, values `traffic.*`/`sensor.id`).
- Próximas unidades en cola: **U6** (Baseline & Report) → U7 → U8 → U9 → U10 → U11.
