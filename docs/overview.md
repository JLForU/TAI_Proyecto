# Panorama del dominio — descubrimiento y monitoreo de activos de red

**Versión:** 3.0  
**Fecha:** 2026-11-05

## 1. Dominio y propósito

Sentinel pertenece al dominio de **network monitoring / asset discovery / observability**. Su finalidad es observar una red autorizada, construir un inventario de activos visibles, medir atributos de red y registrar condiciones que cumplan reglas predefinidas.

El producto no es un SIEM completo, no es un NIDS generalista, no es un escáner de vulnerabilidades y no es una plataforma de gestión de endpoints.

## 2. Capacidades del sistema

1. Descubrimiento periódico de hosts en rangos autorizados.
2. Recolección de IP y MAC cuando el método lo permita.
3. Consulta acotada de puertos y servicios expuestos.
4. Registro del sistema operativo declarado o inferido solo cuando un método habilitado produzca evidencia documentada; de lo contrario, `desconocido`. La huella activa mediante `-O` queda fuera del perfil inicial; sin un método de inferencia habilitado, el valor del MVP será declarado o desconocido.
5. Medición de tráfico IP como bytes/s, IP origen, IP destino y protocolo.
6. Observación separada de actividad ARP y cambios de asociaciones IP↔MAC.
7. Persistencia de inventario, observaciones y eventos.
8. Cálculo de condiciones deterministas en Core; Prometheus evalúa reglas temporales de alerta, Grafana presenta dashboards y Alertmanager administra notificaciones.

## 3. Separación entre observación, evento y alerta

- **Observación:** dato derivado del sondeo o captura (por ejemplo, una respuesta ARP o una medición de bytes en una ventana).
- **Evento:** registro normalizado de una transición o condición (por ejemplo, `ArpMappingChanged` o `AssetFirstSeen`).
- **Alerta:** notificación generada cuando una métrica/evento satisface una regla configurada.
- **Interpretación humana:** el operador determina si el evento responde a una operación legítima, una falla o actividad maliciosa.

Sentinel no convierte automáticamente una alerta en una conclusión sobre intención.

## 4. Modelo de datos observado

| Grupo | Campos | Naturaleza |
|---|---|---|
| Identidad de red | IP, MAC | Observada, con tiempo, interfaz y sensor |
| Sistema operativo | familia/versión | Declarada o inferida solo si un método habilitado aporta evidencia; en caso contrario, desconocida. Registrar método y certeza. |
| Puertos | número, transporte, estado | Observados al momento del sondeo |
| Servicios | protocolo, nombre de servicio y versión opcional | Identificados mediante sondas ligeras cuando hay respuesta; si solo existe correspondencia de puerto, se marca como probable; si no hay evidencia, `desconocido` |
| Tráfico IP | bytes/s, IP origen, IP destino, protocolo | Agregado por ventana; conservar origen/destino en evento/log estructurado |
| ARP | opcode, protocol source/destination, hardware source/destination | Observación de capa 2, separada de flujos IP |
| Evento | id, regla, hora, activo, atributos y evidencia | Determinista |

Las direcciones IP de origen/destino se conservan en los registros estructurados. No se convierten de forma indiscriminada en labels Prometheus porque cada combinación de labels crea una serie temporal y las dimensiones de alta cardinalidad aumentan el volumen almacenado.

## 5. Métodos de recolección y límites

### 5.1 Descubrimiento activo

- ARP dentro del mismo segmento de capa 2.
- ICMP/TCP para verificar disponibilidad según la política del laboratorio.
- Nmap con TCP connect scan (`-sT`), detección ligera de servicio/versión (`-sV --version-light`) y salida XML para procesamiento (`-oX -`), limitado a puertos TCP autorizados. `-sV` envía sondas de aplicación a los puertos abiertos; por eso se trata como sondeo activo y requiere autorización explícita, allowlist, límite de tasa y timeout. Si no hay respuesta suficiente, el servicio o su versión quedan como desconocidos; el nombre deducido solo por número de puerto se marca como probable, no como observado. El sondeo UDP, los scripts NSE (`-sC`/`--script`), el modo agresivo (`-A`) y la detección de SO mediante `-O` quedan fuera del MVP.
- SNMP de solo lectura para dispositivos de red compatibles, si existe una cuenta autorizada; se plantea como mejora posterior.

Todo sondeo activo genera tráfico y puede aumentar carga o aparecer en los logs del objetivo. “Solo lectura” significa que Sentinel no modifica configuración ni estado administrativo del endpoint; no significa que el sondeo sea pasivo o sin impacto. Debe existir autorización explícita sobre rangos, puertos, horario e intensidad, con límites de tasa y timeout.

### 5.2 Captura de tráfico

Se requiere que el sensor reciba tráfico del segmento de interés. Puede lograrse mediante red virtual de laboratorio, mirror/SPAN, TAP o interfaz de captura asignada. Un Pod ordinario no ve automáticamente el tráfico de todos los dispositivos externos. La lectura de sockets `RAW/PACKET` puede requerir `CAP_NET_RAW`; cambiar una interfaz a modo promiscuo puede requerir `CAP_NET_ADMIN`. No se concederán ambas por defecto: el POC debe determinar la necesidad exacta y mantener la captura separada de la administración de interfaces.

La captura se limita a metadatos requeridos: protocolo, direcciones, bytes y campos ARP. Para tráfico IP, `packet_length_bytes` se calcula con la longitud de capa IP (IPv4 `total_length`; IPv6 longitud de payload más la cabecera base), excluyendo la cabecera Ethernet; `bytes_per_second` es la suma de esas longitudes dividida por la duración efectiva de la ventana. ARP se contabiliza como mensajes/s y no se mezcla con bytes/s de flujos IP. El MVP no almacena payloads completos.

### 5.3 Identificación de SO

Nmap puede inferir el SO mediante huellas TCP/IP, pero `-O` requiere privilegios para operaciones con paquetes crudos; por ello no se habilita en el perfil inicial de menor privilegio. Si una prueba posterior autoriza y aísla esos permisos, el resultado seguirá siendo una inferencia y deberá guardarse con método y nivel de certeza. Sin esa modalidad, se conserva `desconocido` salvo evidencia observada o declarada en el laboratorio. La ausencia de resultado no equivale a un error del activo.

### 5.4 Acceso por permisos

- La consulta SNMP debe utilizar credenciales de lectura; preferir SNMPv3 cuando el dispositivo lo soporte.
- Los métodos remotos con credenciales (SSH/WinRM/WMI) no hacen parte del MVP inicial; si se exploran después, deberán tener cuentas de lectura.
- No se instala software residente en los endpoints para esta versión.

## 6. Eventos y alertas previstos

### Eventos registrados

- `AssetFirstSeen`: activo visible que no figuraba en un ciclo exitoso anterior.
- `AssetMissing`: activo esperado que deja de responder durante un número configurable de ciclos exitosos.
- `PortServiceChanged`: cambio observado en puertos/servicios.
- `ArpMappingChanged`: cambio temporal observado en la asociación IP↔MAC.
- `TrafficWindowObserved`: medición de tráfico agregada por ventana.
- `SensorUnavailable`: el Traffic Sensor no envía latidos/ventanas dentro del intervalo esperado.
- `DiscoveryCycleFailed`: un Job de descubrimiento falla o cubre parcialmente el alcance; se registra sin alerta por defecto.

No se registran ausencias cuando el ciclo de descubrimiento falló o cubrió parcialmente el alcance: el inventario debe distinguir “no observado” de “no disponible”.

### Alertas MVP

- `TrafficThresholdExceeded`: tasa de bytes/s superior al criterio configurado.
- `ArpRateThresholdExceeded`: frecuencia de mensajes ARP superior al criterio configurado.
- `ArpMappingChanged`: variación de la asociación IP↔MAC que requiere revisión.
- `SensorUnavailable`: falta de telemetría del Traffic Sensor; no se reutiliza para fallos de Jobs de descubrimiento.

La primera aparición de host y los cambios de puertos/servicios quedan en el inventario/eventos; no generan alerta por defecto en el MVP.

## 7. Escenario de validación ARP

En un laboratorio aislado, los dos dispositivos Android, el equipo macOS y el equipo Windows consultan la página HTTP del servidor Linux. Se incorpora temporalmente un sexto activo de prueba que genera actividad ARP controlada y una asociación IP↔MAC distinta para la IP del servidor. El sensor debe registrar el aumento de mensajes ARP y el cambio observado, con marcas de tiempo. La prueba busca mostrar la secuencia y su latencia aproximada, no demostrar detección general de suplantación ARP.

El tráfico de prueba lo genera un equipo externo a Sentinel; Sentinel no lo produce ni modifica tablas ARP.

## 8. Restricciones de alcance

- Sin clasificación de amenazas ni inteligencia de amenazas.
- Sin controles preventivos o de respuesta aplicados a los activos observados: no hay bloqueo, cuarentena, remediación ni parcheo. Se mantienen RBAC, aislamiento y endurecimiento para los componentes internos de Sentinel.
- Sin gestión de cuentas, software o configuración de endpoints.
- Sin inspección ni almacenamiento de payload en el MVP.
- Sin promesa de identificación exacta de todos los SO o dispositivos.
- Sin garantía de detección general de DDoS, ARP spoofing o cualquier otra familia de ataques.

## 9. Supuestos no validados

- `[INTERNO]` Segmento objetivo de 10–50 activos.
- `[INTERNO]` Cinco activos base para la demostración, más un activo de prueba temporal.
- `[INTERNO]` Agregación de tráfico cada 5 segundos.
- `[INTERNO]` Cinco muestras separadas por 5 segundos para la línea base inicial.
- `TBD` método de acceso al tráfico físico.
- `TBD` intervalo de descubrimiento y límites de tasa.
- `TBD` umbrales y regla estadística final.
- `TBD` retención de logs y datos de inventario.
