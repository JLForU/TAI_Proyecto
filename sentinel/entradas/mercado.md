# Análisis de mercado — monitoreo de activos de red

**Fecha de consulta:** 2026-11-05  
**Estado:** exploración competitiva; no constituye validación de demanda.

## 1. Conclusión ejecutiva

El dominio de descubrimiento de activos, monitoreo de red, métricas y alertas está ampliamente cubierto por herramientas open source y comerciales. Sentinel no presenta una categoría nueva ni una ventaja defendible demostrada. Su oportunidad más razonable, por ahora, es como **prototipo académico reproducible** que integra un subconjunto de estas capacidades sobre Kubernetes.

No se calcula TAM/SAM/SOM porque no existe una fuente específica validada que mida la demanda por una solución equivalente a Sentinel. No se estiman ingresos ni disposición a pagar.

## 2. Alternativas y competidores

| Solución | Capacidades documentadas relevantes | Relación con Sentinel | Límite de la comparación |
|---|---|---|---|
| Zabbix | Descubrimiento por rangos IP, disponibilidad de servicios, componentes residentes y SNMP | Competidor directo en descubrimiento/monitoreo | Es una plataforma más amplia; revisar configuración y coste operativo real |
| LibreNMS | Autodescubrimiento, escaneo SNMP, ARP y descubrimiento de vecinos | Competidor directo, especialmente para redes | Requiere credenciales SNMP y configuración apropiada |
| Nagios XI | Hosts/servicios, checks por plugins, umbrales y notificaciones | Competidor directo en alertas y checks | Oferta comercial con más capacidades que el MVP |
| Prometheus + Grafana | Series temporales, dashboards y reglas/alertas | Tecnología base/integración; no resuelve por sí sola toda la identificación de activos | Requiere exporters y fuentes de telemetría |
| Wazuh | Inventario de hardware/software/puertos mediante un componente residente instalado en los endpoints | Alternativa adyacente, más orientada a seguridad de endpoints | El componente residente y la profundidad del inventario exceden el alcance del prototipo |

## 3. Qué parte del problema ya está resuelta

- Zabbix dispone de descubrimiento de red configurable por rangos y disponibilidad de servicios/SNMP.
- LibreNMS implementa métodos de autodescubrimiento, incluidos SNMP y ARP.
- Nagios XI utiliza checks y umbrales explícitos para estados de hosts/servicios y notificaciones.
- Prometheus y Grafana ofrecen infraestructura estándar de métricas, consultas, dashboards y alerting.
- Wazuh ofrece inventario de endpoints mediante un componente residente instalado en los sistemas; esa modalidad de despliegue excede el alcance del prototipo.

Por tanto, Sentinel no debe afirmar que inventó el descubrimiento, el monitoreo, las reglas o los dashboards.

## 4. Espacio hipotético de Sentinel

El espacio inicial sería una implementación pequeña, self-hosted y acotada a:
- topología de laboratorio o red local autorizada;
- inventario visible por métodos de red;
- atributos de activos (IP, MAC, SO con certeza, puertos y servicios);
- telemetría de tráfico claramente definida;
- un conjunto pequeño de reglas de alertas;
- despliegue reproducible en Kubernetes con Helm y Grafana.

Este espacio es una hipótesis de alcance, no una brecha competitiva confirmada.

## 5. Objeciones que debe superar

1. ¿Por qué no utilizar Zabbix o LibreNMS?
2. ¿Por qué no usar Prometheus/Grafana con exporters y scripts propios?
3. ¿Se justifica Kubernetes para una red de 10–50 activos?
4. ¿Cómo obtiene el sensor visibilidad de la LAN sin permisos excesivos?
5. ¿Qué aporta Sentinel si no instala software residente y no puede conocer con certeza el SO o software de cada endpoint?
6. ¿Qué tasa de falsos positivos producen las reglas de ARP y tráfico?

## 6. Hipótesis ICP y riesgo de adopción

El segmento de 10–50 activos `[INTERNO]` puede ser demasiado pequeño para justificar una plataforma Kubernetes y, al mismo tiempo, demasiado complejo para un script aislado. Esta tensión debe medirse con entrevistas o pruebas de uso; no se asume que exista mercado suficiente.

## 7. Datos no disponibles

- TAM/SAM/SOM específicos: `[VERIFICAR]`.
- Disposición a pagar: `[VERIFICAR]`.
- Precio competitivo y coste total de operación: `[VERIFICAR]`.
- Tasa real de adopción de self-hosted Kubernetes en el ICP: `[VERIFICAR]`.
- Ventaja frente a Zabbix/LibreNMS/Nagios: `[VERIFICAR]`.

## Fuentes

Ver `research/fuentes.md` para enlaces y fecha de consulta. La comparación anterior se limita a capacidades descritas por los propios proyectos/proveedores; no equivale a benchmark de rendimiento ni evaluación práctica.
