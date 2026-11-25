# Build Instructions

## Prerequisites
- **Build Tool**: Python 3.11 (`requires-python = ">=3.11,<3.12"`) + Docker (imagen OCI); no hay etapa de compilación (proyecto puro Python)
- **Dependencies**: `requirements.txt` (55 paquetes pineados: fastapi, pydantic, uvicorn, pytest, ruff, mypy, coverage, hypothesis, weasyprint…); **sin deps nuevas** desde U6
- **Environment Variables** (arranque del Core/sensores; loaders estrictos):
  - `SENTINEL_INGEST_TOKEN`, `SENTINEL_API_BASE` (U5→U2)
  - `SENTINEL_TRAFFIC_*` (U5), `SENTINEL_DISCOVERY_*` (U4)
  - `SENTINEL_BASELINE_*` (U6): `K`, `ABSOLUTE_BPS`, `INTERVAL_SECONDS`, `COLLECTOR_TIMEOUT_SECONDS` — ver `README.md` § Baseline
  - `SENTINEL_DB_PATH`/settings de `CoreSettings` para el Core
- **System Requirements**: Linux (patrón del proyecto); ~500 MB disco para venv + imagen; sin privilegios (la captura AF_PACKET es documented-only)

## Build Steps

### 1. Install Dependencies
```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
# validación local de esta sesión (si se usa el venv pre-armado):
#   /tmp/opencode/venv/bin/{pytest,ruff,mypy,coverage}
```

### 2. Configure Environment
```bash
export SENTINEL_INGEST_TOKEN=<token>
export SENTINEL_API_BASE=http://127.0.0.1:8080
# Opcional (U6): valores desde values.yaml vía U9 en K8s
# export SENTINEL_BASELINE_ABSOLUTE_BPS=<bps>   # obligatorio en values.yaml
```

### 3. Build All Units
No hay binario: la "build" es la verificación estática + la imagen OCI.
```bash
ruff check . && ruff format --check .   # lint + formato
mypy src/sentinel                        # tipos (gradual)
docker build -t sentinel:test .          # artefacto de release
```

### 4. Verify Build Success
- **Expected Output**: `All checks passed!` · `N files already formatted` ·
  `Success: no issues found in 87 source files` ·
  `Successfully tagged sentinel:test`
- **Build Artifacts**:
  - Imagen OCI `sentinel:test` (multi-stage, expone 8080/9108)
  - `.coverage` (tras el suite con `--cov`)
- **Common Warnings**: `StarletteDeprecationWarning` de `httpx` en
  `TestClient` (inofensivo, ya presente en U2–U5); logs
  `baseline_hydration_failed` en la **primera** ejecución con BD nueva
  (tablas aún no creadas ⇒ servicio arranca vacío — degradación FD §3.6;
  en reinicios con datos la hidratación carga los estados)

## Troubleshooting

### Build Fails with Dependency Errors
- **Cause**: Python ≠ 3.11; pip desactualizado; índice corporativo sin un paquete pineado
- **Solution**: usar `python3.11 -m venv`; `pip install -U pip`; verificar `python --version`

### Build Fails with Compilation Errors (mypy/ruff)
- **Cause**: cambios fuera del flujo AIDLC o ediciones sin pasar gates
- **Solution**: `ruff check . --fix && ruff format .` para estilo;
  para mypy, revisar el archivo señalado (la codebase parte en verde — no
  suppress global)

### docker build Falla
- **Cause**: daemon Docker caído o contexto sucio
- **Solution**: `docker info`; revisar `.dockerignore` (el build usa la raíz
  `sentinel/`); CI ejecuta el mismo comando en el job `build`
