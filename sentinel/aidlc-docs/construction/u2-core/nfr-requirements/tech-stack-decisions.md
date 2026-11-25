# Tech Stack Decisions — U2 (Core API, persistence & export)

**Fase**: CONSTRUCTION — NFR Requirements
**Fecha**: 2026-11-11
**Estado**: GENERATED — pendiente de aprobación
**Unidad**: U2 — `src/sentinel/core/`
**Nota**: decisiones de la **unidad**; hereda TS-01..11 de U1 y el stack global de `requirements.md` §4 (FastAPI, SQLite, Python 3.11). Aquí se confirman y se añaden las propias de U2.

---

## 1. Tabla de decisiones

| # | Decisión | Elegida | Alternativas descartadas | Justificación | Origen |
|---|---|---|---|---|---|
| TS-U2-01 | Web framework | **FastAPI + uvicorn (1 worker)** | Flask (sin Pydantic/OpenAPI nativo); Starlette (bajo nivel, sin integración de modelos) | Fijado por NFR-TECH-02/04; OpenAPI auto (MNT-01); Pydantic TS-02 compartido con payloads | requirements §4, Plan Q3=A |
| TS-U2-02 | Acceso a SQLite | **stdlib `sqlite3` + repositorios SQL + WAL + lock de escritura** | SQLAlchemy 2.0 + Alembic (dependencia/peso para lab); aiosqlite (async innecesario con services síncronos) | Control total, cero deps extra, encaja con single-writer (REL-01) | FD Q1=A, Plan Q3=A |
| TS-U2-03 | Migraciones de esquema | **DDL idempotente al arrancar** (`CREATE TABLE IF NOT EXISTS` + índices) | Alembic (overhead para 7 tablas greenfield); scripts manuales sueltos | OQ-02 cerrado con esquema fijo; sin cambios previstos hasta U6/U7 | FD BR-U2-20, domain-entities |
| TS-U2-04 | Tests de API | **FastAPI `TestClient` + SQLite temporal por test** (sin servidor vivo) | uvicorn real en tests (lento, puertos efímeros, frágil); solo mocks (sin cobertura de SQL) | Rapidez + ejercita SQL real; GT con servidor vivo quedan en Build and Test | Plan Q11=A |
| TS-U2-05 | Identidad de eventos | **`uuid.uuid5` stdlib** sobre hash SHA-256 del contenido normalizado | uuid4 + clave natural (no idempotente ante re-normalización); ULID (librería externa) | Determinista, reenvíos ⇒ mismos UUIDs, sin dependencias | FD Q3=A |
| TS-U2-06 | Config de unidad | **`core.config.CoreSettings`** (Pydantic, env `SENTINEL_*`, fail-fast, patrón de `foundation.config`) | Claves sueltas en módulos (sin validación); esquema único global en U2 (rompe BR-06) | Consistencia con U1, 4 claves acotadas | FD Q13=A |
| TS-U2-07 | Auth de ingesta | **Bearer token + `hmac.compare_digest`** (comparación constante) | OAuth2/JWT (issuer, rotación, sin necesidad en lab); mTLS (excede MVP) | IP2 pide token de Secret; una comparación constante cubre el caso | FD Q2=A, Plan Q5=A |
| TS-U2-08 | Export CSV/JSON | **stdlib `csv` + `json` en memoria** | pandas (MBs de deps para 9 columnas); streaming a disco (innecesario en lab) | Cabecera exacta del AC, cero deps, escala PERF-01 | FD Q7=A |
| TS-U2-09 | Reintentos | **`foundation.retry` en los colectores (U4/U5); Core sin retry interno** | Retry en el Core (enmascarea fallos de DB, añade latencia); tenacity (ya cubierto por U1) | Single-owner (REL-03); services.md §2.1 | Plan Q12=A |
| TS-U2-10 | Gate de cobertura | **≥70% en `src/sentinel/core/`** | 60% (menor que U1); 80% (inconsistente con bar de U1); sin gate | Mismo bar que TS-06, verificable | Plan Q10=A |
| TS-U2-11 | Documentación de API | **OpenAPI vivo en `/openapi.json` + `/docs` habilitado en lab** | Solo export en CI (menos cómodo para U3); deshabilitado (peor demo) | Acelera U3 (IP3) y la demo; NFR-OPS-03 complementa con Markdown | Plan Q9=A |

---

## 2. Dependencias previstas de U2 (fijadas en `requirements.txt`)

| Paquete | Uso | Tipo |
|---|---|---|
| `fastapi` | Web framework, OpenAPI | runtime |
| `uvicorn` | Servidor ASGI (1 worker) | runtime |
| `httpx` | Cliente para `TestClient` de Starlette | dev/test |
| `pydantic` | Payloads y settings (TS-02) | runtime (heredado) |
| `pytest`, `pytest-cov`, `hypothesis`, `mypy`, `ruff` | Toolchain heredada de U1 | dev |

> `scapy`, `python-nmap`, `jinja2`, `weasyprint`/PDF pertenecen a U4/U5/U3; U2 no los importa.

---

## 3. Decisiones explícitas pendientes para otras unidades (no se toman aquí)

| Tema | Unidad que decide |
|---|---|
| Tamaño de PVC y values.yaml de la DB | U9 (Infrastructure Design) |
| Evaluación real de latencia/throughput en la demo | Build and Test / U11 |
| Rate limiting, TLS, RBAC de la API | U9/U10 (infra/seguridad) |
| Cuerpos reales de `collect()` en 9108 | U7 (NFR Design/Code) |
| Retención/purga de datos a largo plazo | U11 (post-MVP) |

---

## 4. Approval Gate

**Estado**: GENERATED — pendiente de aprobación (ver mensaje de completitud).
