# PRD — Sentinel

**Versión:** 3.0  
**Fecha:** 2026-11-05  
**Estado:** especificación de producto consolidada; no representa software implementado.

## 1. Visión del producto

### 1.1 One-liner

Sentinel es una plataforma self-hosted de monitoreo de activos de red que descubre dispositivos visibles, registra inventario y telemetría de tráfico, y genera alertas a partir de reglas explícitas, sin modificar los activos monitorizados.

### 1.2 Job to be Done

Cuando necesito conocer qué dispositivos están presentes en una red local y revisar cambios o picos de tráfico, quiero que el sistema actualice automáticamente el inventario y registre las condiciones observadas, para consultar evidencia y recibir alertas sin administrar los endpoints desde la plataforma.

### 1.3 Misión

Proporcionar una implementación cloud-native reproducible para observar activos de una red autorizada, conservar evidencia estructurada y visualizar métricas/alertas. Sentinel prioriza la observación acotada y la claridad sobre qué se midió, cuándo y mediante qué método.

### 1.4 Hipótesis de valor

`[INTERNO]` Una integración de descubrimiento, inventario, métricas, logs y dashboards puede reducir la fragmentación de la operación frente a ejecutar verificaciones manuales independientes. Esta hipótesis debe compararse con Zabbix, LibreNMS y scripts propios.

## 2. Contexto y problema

### 2.1 Problema

Un operador puede carecer de una vista unificada y temporal de activos visibles, sus identificadores de red, puertos/servicios y variaciones de tráfico. La recolección dispersa entre herramientas y scripts dificulta revisar qué cambió y cuándo.

### 2.2 Alternativas actuales

Zabbix, LibreNMS, Nagios, Wazuh, Prometheus y Grafana cubren distintas partes del problema. Sentinel no debe presentarse como sustituto superior sin un benchmark. Su alcance se concentra en integrar un subconjunto reducido sobre Kubernetes.

### 2.3 Por qué Kubernetes

Kubernetes es el plano de despliegue y ejecución de Sentinel. Aloja los servicios, Jobs, sensores, persistencia y stack de observabilidad. Esta decisión responde al objetivo cloud-native del proyecto; no se afirma que Kubernetes sea la opción operativa más barata para toda red pequeña.

## 3. Alcance funcional

### 3.1 Activos y atributos

El MVP descubre activos visibles mediante técnicas autorizadas de red y conserva, cuando sea posible:

- **IP:** dirección observada y marca temporal.
- **MAC:** dirección observada y marca temporal; no se toma como identificador permanente por sí sola.
- **Sistema operativo:** familia/versión declarada en el laboratorio o inferida únicamente cuando un método habilitado y documentado produzca evidencia; incluir método y nivel de certeza. El MVP no ejecuta detección activa `-O`; por defecto, sin declaración/evidencia suficiente se registra `desconocido`.
- **Puertos:** número, transporte y estado observado.
- **Servicios:** protocolo, nombre probable/identificado y versión opcional. La identificación usa sondas ligeras de Nmap (`-sV --version-light`) sobre puertos TCP autorizados; si solo se conoce el puerto, el servicio se etiqueta como probable, y si no hay evidencia suficiente queda `desconocido`.
- **Tráfico:** bytes/s, IP origen, IP destino y protocolo para flujos IP; los mensajes ARP se registran con sus campos de capa 2.

El sistema no garantiza inventario exhaustivo de software, procesos o configuración interna de los endpoints.

**Solo lectura sobre activos:** Sentinel no cambia configuraciones ni estado administrativo de los endpoints. No obstante, ARP/ICMP/TCP y las sondas de servicio (`-sV --version-light`) envían paquetes y pueden producir carga o registros en el objetivo; por eso requieren autorización explícita, allowlist de CIDR/puertos, límites de tasa, timeout y ventanas definidas. El MVP no ejecuta scripts NSE, escaneo UDP, modo agresivo ni detección `-O`.

### 3.2 Tráfico y ARP

El registro de tráfico IP conserva, por observación/ventana:

- `observed_at` en UTC;
- `src_ip` y `dst_ip`;
- `protocol`;
- `bytes_per_second`;
- `interface` y `sensor_id`.

Los eventos estructurados conservan las direcciones IP de origen/destino. Para tráfico IP, `packet_length_bytes` corresponde a longitud de capa IP (IPv4 `total_length`; IPv6 longitud de payload más cabecera base), excluyendo cabecera Ethernet; `bytes_per_second` es la suma de esas longitudes dividida por la duración efectiva de la ventana. Para evitar cardinalidad elevada, las métricas Prometheus no utilizan de forma indiscriminada `src_ip` y `dst_ip` como labels; inicialmente se agregan por protocolo e interfaz.

ARP se modela por separado porque es un protocolo de capa 2. La observación conserva `op`, `psrc`, `pdst`, `hwsrc`, `hwdst`, hora, interfaz y sensor. La frecuencia de mensajes ARP se mide como mensajes/s; ARP no se suma a bytes/s de flujos IP ni se fuerza a un flujo IP ordinario.

### 3.3 Frecuencias iniciales

- Descubrimiento: periódico y configurable; intervalo inicial `TBD`.
- Captura de tráfico: continua durante la ventana de prueba.
- Agregación de tráfico: 5 s como hipótesis inicial `[INTERNO]`.
- Línea base inicial: cinco muestras consecutivas separadas por 5 s, con marcas esperadas `t=5, 10, 15, 20, 25 s` desde el inicio del monitoreo; ventana de inicialización aproximada de 25 s `[INTERNO]`.
- Estadísticos: media `μ` y varianza muestral `s² = Σ(xᵢ−μ)²/(n−1)` con `n=5`; desviación estándar `s = √s²`.
- Umbral de tráfico alto y umbral de actividad ARP: `TBD`; opciones de tráfico a evaluar: valor absoluto, `μ + k·s` con `k` por definir, o combinación.

No se disparan alertas basadas en línea base hasta que esta se encuentre disponible. El cálculo de la condición y la línea base vive en Core/U6; la duración temporal de la alerta pertenece a las `PrometheusRule` de U7, no al sensor (U4). El criterio y la dimensión de agregación (interfaz/protocolo, destino o flujo) deben fijarse tras el POC; no se asignan umbrales arbitrarios.

### 3.4 Eventos y alertas

Los **eventos** conservan los cambios observados en el inventario. Las **alertas** se reservan para condiciones explícitas del MVP.

| Código | Tipo | Condición observada | Resultado en MVP |
|---|---|---|---|
| E-01 | `AssetFirstSeen` | Activo visible que no figuraba en un ciclo exitoso anterior | Registrar en inventario/log; no alerta por defecto |
| E-02 | `AssetMissing` | Activo esperado ausente durante N ciclos de descubrimiento exitosos | Registrar estado; no alerta por defecto |
| E-03 | `PortServiceChanged` | Cambio en puertos/servicios observados | Registrar en historial/log; no alerta por defecto |
| E-04 | `ArpMappingChanged` | Cambia la asociación observada IP↔MAC | Registrar evento y generar alerta para revisión |
| E-05 | `TrafficWindowObserved` | Medición de tráfico agregada por ventana | Registrar métricas/log según regla de retención |
| E-06 | `SensorUnavailable` | El Traffic Sensor deja de enviar latidos/ventanas dentro del intervalo esperado | Registrar evento y generar alerta operativa |
| E-07 | `DiscoveryCycleFailed` | Un Job de descubrimiento termina fallido o parcial | Registrar log/evento; no alerta por defecto |

| Regla | Condición | Texto de alerta permitido | Afirmación prohibida |
|---|---|---|---|
| R-01 `TrafficThresholdExceeded` | Core publica condición verdadera cuando bytes/s supera el umbral disponible; Prometheus aplica la duración `for` configurada antes de disparar | Umbral de tráfico excedido | DDoS/ataque confirmado |
| R-02 `ArpRateThresholdExceeded` | Core publica condición verdadera cuando mensajes ARP/s supera el umbral disponible; Prometheus aplica la duración `for` configurada si se define | Actividad ARP por encima del umbral | ARP flooding malicioso confirmado |
| R-03 `ArpMappingChanged` | Asociación IP↔MAC cambia frente a la observación anterior | Cambio de asociación IP↔MAC | ARP spoofing confirmado |
| R-04 `SensorUnavailable` | Core publica `sentinel_collector_up{collector="traffic"}=0` al superar el plazo de ausencia configurado; Prometheus aplica la duración `for` definida | Sensor sin telemetría | Ataque contra la red confirmado |

La aparición de un activo y los cambios de puertos/servicios quedan registrados, pero no generan alerta por defecto en el MVP. Los fallos de Jobs de descubrimiento se registran como `DiscoveryCycleFailed`; la alerta `SensorUnavailable` queda reservada al Traffic Sensor. La ausencia de un activo solo se registra cuando el ciclo cubrió satisfactoriamente el alcance configurado; un ciclo fallido o parcial no debe presentarse como ausencia del host.

### 3.5 Logs y evidencia

Los logs estructurados conservan fecha/hora, activo o par origen/destino, método, protocolo, condición, regla, umbral, valor medido y resultado. U5 asigna identidad estable a los eventos persistidos y Core usa esa identidad al procesar lotes repetidos para evitar duplicar hechos. U6 proyecta los eventos fuente a indicadores sin crear una segunda copia persistente. Prometheus mantiene el estado de las reglas; Alertmanager agrupa, silencia y enruta las notificaciones. No se almacena payload completo de paquetes en el MVP. El log distingue observación, inferencia, evento y alerta.

## 4. Perfil de cliente ideal

Hipótesis: equipo pequeño de TI/redes/ciberseguridad que administra una red local de 10–50 activos `[INTERNO]`, requiere inventario simple y puede desplegar un entorno Kubernetes self-hosted. El perfil completo, personas, objeciones y vacíos está en `docs/icp.md`.

## 5. Casos de uso principales

### UC-01 — Descubrimiento inicial y periódico

**Actor:** analista/administrador de red.  
**Trigger:** inicio del laboratorio o ejecución del CronJob.  
**Flujo:** valida rangos autorizados → ejecuta descubrimiento → sondea puertos/servicios permitidos → normaliza resultados y certeza → envía observaciones al Core → persiste inventario → expone métricas/logs.  
**Resultado:** catálogo de activos observados con fuente y certeza.

### UC-02 — Reconciliación del inventario

**Trigger:** finalización de un ciclo de descubrimiento exitoso.  
**Flujo:** compara observaciones actuales con inventario previo → registra primera aparición, ausencia o cambio → conserva observación anterior y nueva → actualiza el inventario actual.  
**Resultado:** historial verificable de cambios observados. Si el ciclo falló o cubrió parcialmente el alcance, no marca activos como ausentes.

### UC-03 — Monitoreo de tráfico

**Trigger:** sensor de red en ejecución y conectado a una fuente de captura autorizada.  
**Flujo:** recibe paquetes/metadatos → filtra protocolos admitidos → extrae campos IP o ARP → agrega bytes/s y mensajes ARP/s por ventana → envía agregados al Core → expone métricas y logs.  
**Resultado:** series temporales y eventos con origen, destino, protocolo y marca temporal cuando corresponda.

### UC-04 — Alerta de tráfico alto

**Trigger:** tasa de tráfico supera el criterio configurado.  
**Flujo:** Core calcula condición según umbral/línea base → expone indicador de condición → Prometheus evalúa la regla de alerta → Alertmanager recibe y agrupa la alerta → operador consulta dashboards/logs.  
**Resultado:** aviso de condición de tráfico por encima del umbral, sin atribución de ataque.

### UC-05 — Escenario controlado ARP

**Trigger:** ejecución de prueba autorizada en una red aislada.  
**Flujo:** dos dispositivos Android, un equipo macOS y un equipo Windows consultan normalmente la página HTTP del servidor Linux → se incorpora temporalmente un activo de prueba → el generador externo produce actividad ARP controlada → el sensor registra el aumento de mensajes ARP y la asociación IP↔MAC observada → Core conserva evento y métricas → Prometheus/Alertmanager emiten la alerta configurada.  
**Resultado:** evidencia temporal de la variación. Se espera observar una asociación distinta para la IP del servidor aproximadamente 10 s después del inicio de la prueba `[INTERNO]`; esto valida el escenario controlado, no detección general de suplantación ARP.

## 6. Principios de diseño no negociables

1. **Solo lectura sobre activos:** no ejecutar escrituras ni cambios remotos.
2. **Autorización por alcance:** todo rango, puerto, método y horario de sondeo debe estar aprobado.
3. **Separación entre Kubernetes y endpoints:** Kubernetes despliega los componentes de Sentinel; Sentinel no administra endpoints.
4. **Evidencia determinista:** eventos y alertas surgen de mediciones y reglas versionadas/reproducibles.
5. **Certeza explícita:** distinguir observación directa, inferencia, declaración de laboratorio y dato desconocido.
6. **Captura mínima:** metadatos necesarios; no payload en MVP.
7. **Seguridad del sensor:** no conceder privilegios generales; documentar y probar capabilities específicas.
8. **Trazabilidad:** guardar regla, fuente, hora, umbral, valor y estado del sensor.
9. **Sin respuesta automática:** no bloquear, aislar, parchear ni remediar.

## 7. User journeys

### 7.1 Operador — inicio y revisión

1. El operador abre Grafana.
2. Revisa métricas agregadas del inventario, estado del Traffic Sensor y hora del último ciclo de descubrimiento.
3. Consulta paneles de cambios y cantidades de activos; los datos individuales se obtienen mediante exportación CSV/JSON desde Core.
4. Abre el panel de tráfico por protocolo e interfaz; revisa los registros estructurados exportados para consultar IP origen/destino.
5. Revisa alertas de tráfico, actividad ARP o sensor sin telemetría en Alertmanager.
6. Decide fuera de Sentinel si requiere una investigación adicional.

### 7.2 Administrador — despliegue

1. Revisa valores Helm, rangos, puertos y ventanas autorizadas.
2. Aplica configuración declarativa al namespace.
3. Verifica Pods, Jobs, PVC, ServiceMonitor y reglas.
4. Valida RBAC, cuentas de servicio y capabilities del sensor.
5. Confirma que el sensor solo observa el segmento previsto.

### 7.3 Ciclo fallido

1. Si un Job de descubrimiento falla o termina con cobertura parcial, Core registra `DiscoveryCycleFailed` en logs/inventario y actualiza las métricas del ciclo; ese hecho no genera una alerta por defecto.
2. Si el Traffic Sensor deja de enviar latidos/ventanas, Core expone `sentinel_collector_up{collector="traffic"} = 0`.
3. Prometheus evalúa la regla correspondiente y Alertmanager gestiona la notificación operativa.
4. No se presenta un inventario vacío como si fuera una red sin activos; tampoco se registra `AssetMissing` por un ciclo fallido o parcial.

### 7.4 Evento observado pero ambiguo

1. Sentinel observa pico de tráfico, actividad ARP o cambio de asociación.
2. La regla registra una condición objetiva.
3. El operador revisa fuente, destino, ventana y cambios coincidentes.
4. Sentinel no clasifica intención ni ejecuta respuesta.

## 8. Alcance del MVP — MoSCoW

### Must Have

- Despliegue en Kubernetes.
- Helm chart de Sentinel.
- Descubrimiento de IP/MAC en rangos autorizados.
- Sondeo acotado de puertos y servicios.
- Campo SO con método y certeza.
- Captura/medición de metadatos de tráfico en el segmento de laboratorio, mediante una fuente de visibilidad validada.
- Métrica de bytes/s, IP origen, IP destino y protocolo en observaciones/logs.
- Observación separada de mensajes ARP y asociaciones IP↔MAC.
- Inventario, observaciones y eventos persistidos.
- Reglas deterministas de tráfico alto, actividad ARP/cambio IP↔MAC y pérdida de telemetría.
- Prometheus, Alertmanager y Grafana mediante Helm.
- Logs estructurados.
- Core con API interna de ingesta, exportación CSV/JSON y endpoint `/metrics`.
- RBAC mínimo, cuentas separadas y capabilities de contenedor justificadas.
- Pruebas de ausencia de escrituras sobre endpoints.
- Escenario controlado de tráfico alto y escenario ARP de laboratorio.

### Should Have

- SNMP de solo lectura para uno o más dispositivos de red.
- Exportación de eventos como CSV/JSON.
- Alertmanager con un canal de notificación externo.
- NetworkPolicies para aislar la comunicación interna de Sentinel, según capacidades del CNI.
- GitOps con Argo CD si el tiempo del proyecto lo permite.

### Could Have

- Más de un sensor o subred.
- Panel de topología.
- Integración de logs en Loki.
- Retención y backup configurables.
- Detección de tecnología vecina (LLDP/CDP) si el equipo de red lo soporta.

### Won't Have

- Identificación/clasificación de amenazas o uso de inteligencia de amenazas.
- Detección general de ataques o garantía de detección de DDoS/ARP spoofing.
- Controles preventivos o de respuesta sobre los activos: bloqueo, aislamiento, contención o remediación. Se mantienen RBAC, NetworkPolicy y endurecimiento del despliegue de Sentinel.
- Gestión de endpoints, cuentas, servicios, procesos o configuraciones.
- Escaneo de vulnerabilidades y parcheo.
- Instalación obligatoria de software residente en todos los dispositivos.
- Inspección/almacenamiento de payloads.
- SIEM/NDR completo.

Las funciones excluidas pueden reconsiderarse en una versión futura solo mediante alcance independiente, autorización explícita, modelo de permisos y evaluación de impacto; no se asumen como parte de esta entrega.

## 9. Módulos funcionales

| Módulo | Responsabilidad | Entrada/salida |
|---|---|---|
| M1 Configuración y alcance | Rangos, puertos, ventanas, filtros y umbrales autorizados | ConfigMap/Helm values + validación |
| M2 Descubrimiento | ARP/ICMP/TCP/Nmap; SNMP opcional posterior | Observaciones de activos enviadas al Core |
| M3 Sensor de tráfico | Captura de metadatos y agregación temporal | Agregados y observaciones ARP enviados al Core |
| M4 Core e inventario | API de ingesta/consulta, normalización, comparación, historial y persistencia; implementa la exportación estructurada a partir del repositorio de U5 | SQLite/PVC + eventos y exportaciones CSV/JSON |
| M5 Condiciones deterministas | Calcula condiciones de dominio a partir de agregados, línea base e historial; proyecta los eventos existentes a indicadores sin duplicarlos | Indicadores para Prometheus |
| M6 Exposición de métricas | Publica en `/metrics` indicadores agregados de inventario, tráfico, disponibilidad del colector y condiciones de dominio; no expone IP/MAC como labels de alta cardinalidad | Service ClusterIP `sentinel-core`, puerto nombrado `metrics:9108` y ServiceMonitor; el detalle CSV/JSON pertenece a M4/U5 |
| M7 Observabilidad y alertas | Evalúa temporalmente las condiciones mediante `PrometheusRule`, presenta dashboards y administra agrupación, silencios y enrutamiento de notificaciones | Prometheus + Grafana + Alertmanager |
| M8 Runtime Kubernetes | CronJobs/Jobs/Deployments/Services/ConfigMaps/Secrets/PVC; una imagen OCI común con comandos separados; consulta de estado de cargas desde Python | Clúster, API Kubernetes y Helm |
| M9 Seguridad y pruebas | RBAC de lectura, NetworkPolicy, Pod Security, capabilities y pruebas negativas | Evidencia verificable |

## 10. Métricas de éxito

| Métrica | Definición | Meta inicial |
|---|---|---|
| Cobertura de descubrimiento | activos del ground truth detectados / activos esperados | TBD tras POC |
| Precisión de inventario | observaciones correctas / observaciones registradas | TBD tras POC |
| Latencia de alerta | tiempo entre condición inyectada y alerta recibida | TBD; medir en laboratorio |
| Error de captura | tiempo sin sensor / tiempo esperado | TBD |
| Ruido | alertas no accionables por hora | TBD |
| No modificación de endpoints | cambios de estado originados por Sentinel | 0 por diseño y prueba |

## 11. Plan de evaluación técnica

### 11.1 Ground truth de laboratorio

Inventario esperado manual para los activos de prueba, puertos y servicios controlados. Capturas o generadores de tráfico documentados. Casos: normal, nuevo host, host ausente, cambio de puerto/servicio, cambio IP/MAC, tráfico bajo, tráfico alto, aumento de ARP, ruido legítimo, sensor caído y error de permisos.

### 11.2 Criterios

- Precisión y recall de descubrimiento dentro del segmento de laboratorio.
- Correctitud de parseo de IP/MAC/puertos/servicios.
- Correctitud de bytes/s y etiquetas de protocolo en tráfico sintético.
- Correctitud de mensajes ARP/s y asociaciones observadas.
- Detección de condiciones por umbral sin atribuir intención.
- Tasa de alertas falsas y latencia.
- Ausencia de escrituras o cambios remotos en los activos.

### 11.3 Revisión

Cada prueba se ejecuta con ground truth conocido y evidencia: configuración, hora, log, métrica, alerta y resultado esperado/real.

## 12. Riesgos y mitigaciones

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Herramientas existentes resuelven el problema | Alta | Alto | Benchmark acotado; justificar el valor de la integración |
| Kubernetes agrega complejidad | Alta | Alto | Pocos workloads; evitar microservicios innecesarios |
| No se obtiene visibilidad de LAN | Alta | Alto | POC de bridge/SPAN antes de desarrollar dashboards |
| SO inferido incorrecto | Media | Medio | Campo de certeza, método y `desconocido` |
| Permisos de captura excesivos | Media | Alto | Sensor aislado, capabilities mínimas, revisión de Pod Security |
| Alertas ruidosas | Alta | Medio | Umbral configurable, ventanas, deduplicación y medición |
| Captura expone datos privados | Media | Alto | Metadatos mínimos, sin payload, retención limitada |
| Sondeo afecta los activos | Media | Alto | Rango/puertos autorizados, rate limiting, horarios y prueba previa |
| Persistencia insuficiente | Media | Medio | PVC, copia de inventario y retención declarada |
| Ciclos parciales generan falsos ausentes | Media | Alto | Marcar ausencias solo tras ciclos completos y exitosos |

## 13. Plan de entrega

- **Linux y contenedores:** scripts de descubrimiento y sensor empaquetados en imagen mínima.
- **Kubernetes/CKA:** namespaces, Jobs, Deployments, Services, PVC, red y troubleshooting.
- **CKAD/Helm:** chart de Sentinel y configuración declarativa.
- **CKS/KCSA:** RBAC, Pod Security, NetworkPolicy, secretos, supply chain y capabilities mínimas.
- **CI/CD/GitOps:** pipeline de pruebas, build, análisis de imagen y despliegue; Argo CD sujeto al tiempo disponible.
- **Observabilidad:** métricas, logs, Prometheus, Grafana y Alertmanager.
- **Sustentación:** descubrimiento reproducible, alerta por tráfico alto, evento ARP, prueba de no modificación de activos y exposición de límites.
