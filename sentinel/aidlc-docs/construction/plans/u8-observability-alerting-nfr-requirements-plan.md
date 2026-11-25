# NFR Requirements Plan — U8 (Observability & alerting)

**Fase**: CONSTRUCTION — NFR Requirements (Part 1 + Part 2)
**Fecha**: 2026-11-24
**Estado**: APPROVED (Q1=A, Q2=A, Q3=A)
**Workspace root**: `/home/jhoseph/Documents/TAI/TAI_Proyecto/sentinel`

## 1. Pasos de requisitos NFR
- [x] **Step 1**: Especificar disponibilidad y resiliencia (`NFR-AVAIL-01`, `NFR-AVAIL-02`) ante pérdida de señal del sensor y reinicios de pods.
- [x] **Step 2**: Especificar rendimiento y cardinalidad (`NFR-PERF-03`, `SCAL-01`) sin etiquetas de alta cardinalidad (IP, MAC, puerto).
- [x] **Step 3**: Especificar seguridad y mantenibilidad (`NFR-SEC-01`, `FR-SEC-02`, `NFR-OPS-01`, `NFR-OPS-03`) con validación local sin requerir `kind` activo en este paso.
