# Imagen OCI única de Sentinel (EN-05, BR-25/BR-26) — Alpine + usuario no-root.
# Entrypoints por módulo (imagen única, comandos separados):
#   docker run --rm sentinel:test python -m sentinel.core
#   docker run --rm sentinel:test python -m sentinel.discovery
#   docker run --rm sentinel:test python -m sentinel.traffic
FROM python:3.11-alpine

RUN adduser -D -u 10001 sentinel

WORKDIR /app

# WeasyPrint (reporte PDF U3): libs de render de fuentes/pango (ID-U3-01).
# nmap (U4): binario del escáner discovery (ID-U4-01) en la misma capa.
RUN apk add --no-cache pango cairo gdk-pixbuf fontconfig ttf-dejavu nmap

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
ENV PYTHONPATH=/app/src

USER sentinel

CMD ["python", "-m", "sentinel.core"]
