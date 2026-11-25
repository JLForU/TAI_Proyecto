# Decisiones pendientes y límites técnicos

**Fecha:** 2026-11-05  
**Estado:** alcance de producto consolidado; las siguientes decisiones requieren pruebas de concepto o configuración final.

## 1. Visibilidad de la red

Kubernetes no hace visible por defecto toda la red física a un Pod. El proyecto debe definir cómo llega al sensor el tráfico de la red de laboratorio:

1. **Red virtual de laboratorio / bridge:** opción preferida para el MVP si los activos de prueba pueden conectarse a un segmento que el sensor pueda observar.
2. **Mirror/SPAN o TAP:** opción para observar una LAN física; requiere que el switch o la infraestructura permita replicar el tráfico.
3. **Interfaz asignada al nodo o modo `hostNetwork`:** técnicamente posible en algunos entornos, pero amplía privilegios y superficie de riesgo; no se adopta sin prueba y justificación.

**TBD:** mecanismo definitivo. No debe afirmarse que un Deployment común captura paquetes de todos los dispositivos de la LAN. Si se selecciona `hostNetwork`, revisar que el comportamiento de NetworkPolicy depende del CNI y puede no aplicar al Pod de la forma esperada.

## 2. Sondeo de puertos y servicios; identificación del SO

La modalidad inicial para TCP es Nmap `-sT -sV --version-light -p <allowlist> -oX -`. `-sT` usa la llamada `connect` del sistema operativo; `-sV` envía sondas de aplicación a los puertos abiertos para identificar servicio/versión y `--version-light` reduce la intensidad de esas sondas. La identificación de servicio es, por tanto, un sondeo activo: debe limitarse a CIDR/puertos autorizados, tasa, timeout y ventana. Una coincidencia deducida solo del número de puerto se marca como probable; sin respuesta suficiente, el servicio/versión queda `desconocido`. No se ejecutan `-sU`, `-sC`, `--script`, `-A` ni `--allports` en el MVP.

La detección remota de SO con `-O` utiliza huellas TCP/IP y requiere permisos para operar con paquetes crudos; no se habilita en el perfil inicial de menor privilegio.

**Decisión:** guardar el SO como `observado`, `inferido`, `declarado-en-laboratorio` o `desconocido`, con el método correspondiente. No inventar un SO cuando no se pueda determinar. **TBD:** establecer si el POC justifica habilitar `-O` y la capability adicional en el Discovery Worker; de lo contrario, mantenerlo desactivado.

## 3. Identificación de activos móviles

Los dispositivos móviles pueden usar direcciones MAC privadas/aleatorias. La identidad del activo no debe basarse únicamente en MAC. Para el MVP, el identificador será una identidad de observación compuesta y temporal `[INTERNO]` (por ejemplo, IP/MAC/ventana de observación), sin asociarla a una persona.

## 4. Tráfico, muestras y umbrales

Se conserva el registro de tráfico IP como `bytes/s + source IP + destination IP + protocol`. La unidad y el cálculo de `packet_length_bytes`/`bytes_per_second` se definen una sola vez en `specs/prd.md`, sección 3.2. Los pares origen/destino se guardan en observaciones y logs estructurados; no se usan como etiquetas Prometheus por su cardinalidad potencial. ARP se registra por separado como mensajes/s con opcode y campos `psrc`, `pdst`, `hwsrc` y `hwdst`; no se suma a bytes/s de tráfico IP.

**Hipótesis de muestreo:** agregación cada 5 s `[INTERNO]`. La cantidad de muestras, sus marcas temporales y el cálculo estadístico de la línea base se mantienen conforme a `specs/prd.md`, sección 3.3; deben validarse con tráfico normal del laboratorio.

**TBD:** criterio final de alerta. Opciones a probar con datos de laboratorio: umbral absoluto configurable; `μ + k·s` con `k` por definir; o combinación de ambos. No se disparan alertas de tráfico hasta que la línea base esté disponible, salvo que se seleccione explícitamente un umbral absoluto independiente.

**TBD:** unidad de agregación para el umbral (por interfaz/protocolo, destino o flujo). Las IP no se convierten en labels de Prometheus sin un análisis de cardinalidad.

## 5. Captura de paquetes y permisos

**Decisión de privacidad:** extraer metadatos necesarios (tiempo, protocolo, origen/destino, tamaño, tasa y campos ARP relevantes) y no persistir payload completo en el MVP. La captura debe tener filtros, límites de tasa y retención definidos.

**TBD:** verificar por separado las capabilities Linux necesarias para Discovery Worker (por ejemplo, sondeo ARP) y Traffic Sensor (captura de sockets `RAW/PACKET`). `CAP_NET_RAW` permite usar sockets RAW/PACKET; `CAP_NET_ADMIN` incluye configuración de interfaces y modo promiscuo. El MVP no concede `CAP_NET_ADMIN`: el feed debe llegar ya replicado o configurado. No conceder `privileged: true`. Separar RBAC Kubernetes de capabilities Linux. Los perfiles Pod Security Baseline y Restricted no permiten añadir `CAP_NET_RAW` explícitamente. Si el POC demuestra que un colector necesita esa capability, mover solo ese workload a `sentinel-capture` no basta: la política Pod Security Admission de ese namespace también debe configurarse para no contradecir la excepción, y una política de admisión complementaria debe mantener las demás restricciones, permitir solo `CAP_NET_RAW` al workload autorizado y rechazar `privileged`, host namespaces, `hostPath`, `CAP_NET_ADMIN` y demás capabilities. El RBAC debe limitar quién crea o modifica workloads en ese namespace. Si no se puede demostrar esa cadena de controles, el feed debe entregarse sin requerir `CAP_NET_RAW` dentro del Pod.

## 6. Integración entre colectores y Core

**Decisión propuesta:** Discovery Worker y Traffic Sensor envían observaciones por HTTP interno al servicio ClusterIP de Sentinel Core. El Core valida, normaliza y persiste en SQLite; es el único escritor de la base de datos.

- API interna inicial: puerto `8080`.
- Endpoint de métricas: puerto `9108` (`/metrics`).
- Autenticación del envío: token almacenado en Secret Kubernetes; nunca en imagen, ConfigMap o logs.
- Los colectores no requieren acceso al API server y deben usar `automountServiceAccountToken: false`.

**TBD:** definir esquema definitivo, límites de lote, timeout, reintentos e idempotencia. No se permite escritura directa de los colectores al PVC. Core es una réplica escritora en el MVP. Si un colector se mueve a `sentinel-capture`, su Secret debe existir también en ese namespace mediante el mecanismo de gestión de secretos elegido; no se deben copiar valores en texto plano al repositorio.

## 7. Almacenamiento y retención

Propuesta inicial: SQLite en PVC para inventario y eventos; métricas en Prometheus; logs operativos en stdout/stderr. Core mantiene una sola réplica escritora. Esta es una opción de laboratorio, no una declaración de arquitectura de producción.

**TBD:** tamaño del PVC, retención de muestras/eventos, rotación de logs y backup. No añadir réplicas del Core mientras SQLite sea la única persistencia sin definir un mecanismo de escritura concurrente.

## 8. Canales de alerta

Prometheus evalúa reglas publicadas y envía alertas a Alertmanager. Grafana se utiliza para consultar métricas y dashboards. El canal de notificación externo (correo/webhook) queda `TBD`; en el MVP puede validarse el estado en la interfaz de Alertmanager y los paneles de Grafana.

## 9. Topología de activos de demostración

La topología prevista contiene cinco activos base: dos dispositivos Android, un servidor Linux, un equipo macOS y un equipo Windows. Los cuatro clientes (dos Android, macOS y Windows) consultan la página HTTP del servidor Linux. Para el escenario ARP se agrega temporalmente un sexto activo de prueba. La forma real de virtualizar o emular Windows/macOS/Android debe definirse según hardware, hipervisor y licencias; no se asumirá que una imagen Linux o un contenedor representa nativamente esos sistemas operativos.

## 10. Escenario controlado ARP y tráfico alto

El escenario se ejecuta en una red de laboratorio aislada y autorizada. Los cuatro clientes (dos Android, macOS y Windows) consultan normalmente la página HTTP del servidor Linux. Luego se incorpora temporalmente el activo de prueba, que genera tráfico ARP controlado y una asociación IP↔MAC distinta para la IP del servidor. El sensor registra el aumento de mensajes ARP y, cuando se observa, el cambio de asociación; se espera ilustrar la variación aproximadamente 10 s después de iniciar la prueba `[INTERNO]`.

El generador externo realiza la actividad del escenario; Sentinel solo observa, registra y alerta. El resultado se describe como condición consistente con el escenario inyectado, no como detección general de suplantación ARP.

## 11. Decisiones de producto no negociables

- Sentinel no realiza escrituras en los activos monitorizados. Los sondeos activos sí envían paquetes de consulta y pueden generar carga/logs; por eso el alcance debe estar autorizado y limitado.
- No cambia reglas de firewall ni listas de control de acceso.
- No bloquea conexiones ni desconecta dispositivos.
- No detiene procesos ni administra servicios remotos.
- No instala software residente en los endpoints en el MVP.
- No escanea vulnerabilidades ni aplica parches.
- No denomina automáticamente `ataque` a cualquier cambio o pico; registra la condición exacta observada.

## 12. Supuestos heredados que se conservan con cautela

- Red local de demostración y cinco activos base: `[INTERNO]`.
- Segmento objetivo de 10–50 activos: hipótesis de ICP, no prueba de escalabilidad.
- Agregación cada 5 s y cinco muestras de línea base: hipótesis por validar.
- Escenario de alteración ARP controlado: prueba de laboratorio, no prueba de detección general de ataques.
