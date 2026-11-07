# U4 — Plan de construcción: sensor de tráfico

**Fase:** construcción detallada, parte 1  
**Versión:** 3.0 · **Fecha:** 2026-11-05  
**Unidad:** U4 — Sensor de tráfico y ARP

## 1. Objetivo

Implementar un sensor Python que consuma una fuente de paquetes autorizada, extraiga únicamente metadatos IP/ARP, agregue el tráfico por ventanas de 5 s y remita lotes al Sentinel Core. La prueba unitaria debe funcionar con fixtures/PCAP sin privilegios. La captura real se habilita solo tras comprobar la interfaz y los permisos requeridos.

El sensor no escribe SQLite y no publica un endpoint Prometheus propio. El Core recibe sus observaciones por `POST /internal/v1/traffic-observations` en `8080`, persiste los datos y expone las métricas en `/metrics` por `9108`.

## 2. Historias incluidas

| Historia | Alcance de U4 |
|---|---|
| SN-016 | Abstracción de fuente de paquetes |
| SN-017 | Parser de metadatos IP/ARP |
| SN-018 | Agregación de bytes/s y mensajes ARP/s por ventana |
| SN-019 | Integración de métricas a través de Core `/metrics` |
| SN-020 | POC de captura real y envío al Core |

U4 no es titular de SN-039, SN-045 ni SN-046. U8 controla las capabilities; U9 ejecuta las pruebas integrales de laboratorio.

## 3. Dependencias y contratos

- **U1:** modelos tipados, configuración validada, logger y nombres/tipos de métricas.
- **U2:** imagen, configuración, Service ClusterIP y contrato de ingesta del Core.
- **U8:** revisión de capabilities y aislamiento de la carga de captura.
- **U9:** validación integral de las pruebas de tráfico y ARP.

### 3.1 Contrato de observación de paquete

Campos posibles, según protocolo y capa disponible:

- `observed_at` en UTC;
- `sensor_id`, `capture_interface`;
- `network_layer_protocol` y protocolo de transporte cuando exista;
- `src_ip`, `dst_ip` para paquetes IP;
- `src_port`, `dst_port` cuando exista TCP/UDP;
- `packet_length_bytes` según la definición de capa IP de `specs/prd.md`, sección 3.2;
- para ARP: `op`, `psrc`, `pdst`, `hwsrc`, `hwdst`.

No se almacena payload, contenido de aplicación, cookies ni credenciales. Los campos IP no se convierten indiscriminadamente en labels Prometheus.

### 3.2 Contrato de agregado

- tráfico IP: bytes/s, `src_ip`, `dst_ip`, protocolo, interfaz, sensor y comienzo/fin de ventana;
- ARP: número de mensajes por segundo, interfaz, sensor y distribución por opcode;
- ventana inicial: 5 s `[INTERNO]`;
- el Core recibe agregados en lotes. Tamaño máximo, timeout, reintento e idempotencia siguen `TBD`.

La comparación temporal de asociaciones IP↔MAC no pertenece a U4: el parser extrae cada observación ARP sin decidir si la asociación cambió. U5 realiza la comparación histórica.

## 4. No objetivos

- No almacenar payloads ni inspeccionar contenido de aplicación.
- No bloquear, descartar o modificar paquetes.
- No comparar asociaciones IP↔MAC previas ni generar `ArpMappingChanged`.
- No atribuir intención o clasificar amenazas.
- No capturar tráfico general de un nodo sin autorización.
- No acceder directamente a SQLite.
- No exponer `/metrics` desde el sensor.
- No usar `privileged: true` como solución inicial.

## 5. Organización de código propuesta

```text
src/sentinel/traffic/
├── __init__.py
├── models.py              # PacketObservation, ArpObservation, TrafficAggregate
├── source.py              # protocolo PacketSource
├── pcap_source.py         # lectura PCAP/fixtures
├── scapy_source.py        # adaptador de captura real, aislado
├── packet_parser.py       # extracción de metadatos por paquete
├── arp_parser.py          # extracción de campos ARP sin comparación histórica
├── aggregator.py          # ventanas de bytes/s y mensajes ARP/s
├── core_client.py         # envío HTTP de lotes al Core
└── service.py             # ciclo de vida del sensor

tests/unit/traffic/
├── test_packet_source.py
├── test_pcap_source.py
├── test_packet_parser.py
├── test_arp_parser.py
├── test_traffic_aggregation.py
└── test_core_client.py

tests/integration/
└── test_capture_interface.py
```

Los nombres son una propuesta inicial. Antes de crear un archivo, comprobar si ya existe un módulo con la misma responsabilidad.

## 6. Interfaces propuestas

### 6.1 Fuente de paquetes

```python
from collections.abc import Iterator
from typing import Protocol

class PacketSource(Protocol):
    def read_packets(self) -> Iterator[object]:
        """Yield packets from a configured, authorized source."""
```

### 6.2 Cliente de ingesta Core

```python
class CoreIngestionClient(Protocol):
    def submit_traffic_observations(self, batch: list[dict]) -> str:
        """Submit a batch and return the Core batch identifier."""
```

El token del colector se inyecta desde un Secret; no se imprime ni se persiste en logs.

### 6.3 Métricas publicadas por Core

U4 entrega datos; Core es quien expone métricas. Contrato inicial esperado:

```text
sentinel_traffic_bytes_per_second{protocol,interface}
sentinel_arp_messages_total{operation,interface}
sentinel_arp_messages_per_second{interface}
sentinel_collector_up{collector}
```

Las métricas de cambios históricos y condiciones de umbral se generan en Core/U5/U6, no en el parser de U4. Las IP origen/destino se conservan en observaciones/eventos estructurados.

## 7. Pasos de construcción

### Paso 1 — Modelos y contrato de fuente

**Tarea:** definir `PacketObservation`, `ArpObservation`, `TrafficAggregate` y `PacketSource`.

**Verificación:**

```bash
pytest -q tests/unit/traffic/test_packet_source.py
```

Los casos deben demostrar consumo de una fuente sintética sin abrir sockets ni requerir capabilities.

### Paso 2 — Fuente PCAP reproducible

**Tarea:** implementar lectura de PCAP/fixtures manteniendo orden y timestamps.

**Verificación:**

```bash
pytest -q tests/unit/traffic/test_pcap_source.py
```

El resultado esperado debe ser determinista para una captura versionada de prueba.

### Paso 3 — Parser IP

**Tarea:** extraer timestamps, protocolo, IP origen/destino y longitud de capa IP. Ignorar payload. Los puertos/servicios del inventario corresponden al descubrimiento TCP de U3; U4 no duplica el catálogo de servicios.

**Verificación:**

```bash
pytest -q tests/unit/traffic/test_packet_parser.py
```

Incluir pruebas para IPv4/IPv6, protocolos no TCP/UDP, paquetes truncados y ausencia de campos. Un test negativo debe comprobar que el objeto serializado no contiene payload.

### Paso 4 — Parser ARP

**Tarea:** extraer `op`, `psrc`, `pdst`, `hwsrc`, `hwdst`, timestamp e interfaz. No comparar con observaciones anteriores.

**Verificación:**

```bash
pytest -q tests/unit/traffic/test_arp_parser.py
```

El parser produce una observación por mensaje ARP y no emite `ArpMappingChanged`.

### Paso 5 — Agregación por ventanas

**Tarea:** calcular bytes/s para tráfico IP y mensajes ARP/s por separado, con ventana inicial de 5 s `[INTERNO]`.

**Verificación:**

```bash
pytest -q tests/unit/traffic/test_traffic_aggregation.py
```

Las pruebas cubren ventanas vacías, tráfico mixto, límites temporales y cálculo exacto con fixtures. La implementación debe respetar la definición de `packet_length_bytes` del PRD (IPv4 `total_length`; IPv6 longitud de payload más cabecera base; se excluye Ethernet) y aplicarla de forma consistente. El cálculo de línea base y los umbrales pertenecen a U6, no a este sensor.

### Paso 6 — Envío de lotes al Core

**Tarea:** enviar agregados y observaciones al endpoint interno del Core `POST /internal/v1/traffic-observations` mediante el Service `sentinel-core:8080`.

**Verificación:**

```bash
pytest -q tests/unit/traffic/test_core_client.py
```

La prueba de integración valida respuesta de aceptación, rechazo de token inválido, timeout y reintento sin duplicación de lote. Los detalles exactos del contrato HTTP siguen sujetos a la decisión de U2.

### Paso 7 — Comprobar métricas desde Core

**Tarea:** verificar que Core persiste el lote recibido y refleja los agregados en `/metrics`.

**Verificación:**

```bash
kubectl port-forward svc/sentinel-core 9108:9108 -n sentinel
# En otra terminal:
curl -fsS http://127.0.0.1:9108/metrics | grep sentinel_traffic_bytes_per_second
curl -fsS http://127.0.0.1:9108/metrics | grep sentinel_arp_messages_total
```

La métrica procede del Core, no de un servidor HTTP del sensor.

### Paso 8 — POC de fuente de captura real

**Tarea:** probar el adaptador Scapy en la interfaz/feed seleccionado y comprobar que los datos llegan a Core. Esta tarea depende del bridge, mirror/SPAN/TAP o interfaz asignada.

**Verificación:**

```bash
pytest -m integration tests/integration/test_capture_interface.py
```

Si no existe feed/interfaz accesible, el test debe quedar `SKIP` con causa explícita. No puede reportarse como captura real exitosa usando únicamente un PCAP offline.

## 8. Trazabilidad de tareas

| Paso | Historia | Archivos esperados | Verificación |
|---|---|---|---|
| 1 | SN-016 | `models.py`, `source.py` | test de fuente |
| 2 | SN-016 | `pcap_source.py` | test PCAP |
| 3 | SN-017 | `packet_parser.py` | test parser IP/no-payload |
| 4 | SN-017 | `arp_parser.py` | test parser ARP |
| 5 | SN-018 | `aggregator.py` | test de ventanas |
| 6 | SN-019 | `core_client.py` | test cliente/contrato API |
| 7 | SN-019 | contrato Core `/metrics` | port-forward + curl |
| 8 | SN-020 | `scapy_source.py` | test de integración o SKIP justificado |

**Prerrequisito externo:** SN-039, de U8, valida capabilities y aislamiento. No se marca U4 completo si captura real es requisito del escenario y el feed no se ha probado.

**Validación integral posterior:** SN-045 y SN-046, de U9, prueban los escenarios de tráfico alto y ARP sobre la arquitectura completa. No son tareas internas de U4.

## 9. Condiciones de finalización

U4 se considera terminada cuando:

1. parser IP y ARP pasan sus pruebas unitarias;
2. agregados de tráfico IP y ARP se calculan por separado;
3. el sensor remite lotes al Core y no escribe SQLite;
4. Core expone las métricas esperadas en `/metrics`;
5. no se conserva payload;
6. la fuente real se prueba en el entorno de laboratorio o se registra de forma explícita que la demostración utiliza PCAP sintético;
7. las capacidades requeridas quedan documentadas por U8 y no se activa `privileged: true`.

**Riesgo técnico principal:** un sensor funcional con PCAP no demuestra que el Pod vea el tráfico de la LAN. La prueba del feed/interfaz es condición separada y obligatoria para declarar captura real.
