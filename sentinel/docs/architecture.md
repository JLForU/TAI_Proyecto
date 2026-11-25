# Arquitectura de Sentinel

Sentinel es una plataforma determinista de monitoreo de activos de red sobre Kubernetes, sin componentes de IA/LLM (`AR-AI-01..05`).

## Módulos principales (`src/sentinel/`)
- `foundation`: configuración, modelos, logging estructurado, reintentos y contrato de métricas (14 familias).
- `core`: API REST/JSON (`/api/v1`), persistencia SQLite sobre PVC, deduplicación, consultas, exportación y servidor de métricas en `:9108/metrics`.
- `gui`: interfaz web server-rendered (FastAPI + Jinja2 + HTMX + Tailwind/DaisyUI) y reportes Markdown/PDF.
- `discovery`: escaneo de alcance (`explicit_hosts`/CIDR) y recolección de inventario/servicios.
- `traffic`: agregación de tráfico y observaciones ARP con soporte de captura/simulación y fixtures.
- `baseline`: línea base estadística, supresión inicial e indicadores deterministas de condición.
