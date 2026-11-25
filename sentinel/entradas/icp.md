# Ideal Customer Profile — Sentinel

**Fecha:** 2026-11-05  
**Estado:** hipótesis inicial; no validada mediante entrevistas.

## ICP — segmento beachhead

Organización o laboratorio que administra una red local de aproximadamente **10–50 activos** `[INTERNO]`, tiene una persona o pequeño equipo responsable de TI/redes/ciberseguridad y necesita inventario observable y alertas básicas, con despliegue self-hosted.

### Condiciones técnicas

- Tiene autorización sobre la red que se va a observar.
- Puede definir rangos IP, horarios y límites de sondeo.
- Puede proporcionar un segmento de captura mediante bridge de laboratorio, TAP o SPAN, o acepta empezar con descubrimiento activo limitado.
- Puede operar un clúster Kubernetes de laboratorio o acepta que esa exigencia proviene del alcance académico, no de una necesidad demostrada del usuario.
- Acepta que el SO pueda quedar como inferido/desconocido sin acceso autenticado al endpoint.

### Firmographics por validar

- País/ciudad: TBD.
- Sector: TBD.
- Tamaño de la organización: TBD.
- Tamaño del equipo de TI/ciberseguridad: TBD.
- Presupuesto anual para monitoreo: TBD.
- Requisitos regulatorios: TBD.

## Buyer personas

### 1. Responsable de infraestructura, redes o ciberseguridad

**Rol:** decisor técnico y principal veto de confianza.  
**Necesita:** visibilidad básica, trazabilidad, control del alcance de sondeo y certeza de que el sistema no modifica activos.  
**Veto:** permisos excesivos, impacto sobre la red, captura no autorizada o alertas ruidosas.

### 2. Analista de red / ciberseguridad

**Rol:** usuario principal.  
**Necesita:** ver activos, cambios de IP/MAC, puertos/servicios, tendencias de tráfico, logs y alertas.  
**Frustración hipotética:** scripts inconexos y evidencia que no queda centralizada.

### 3. Administrador de sistemas

**Rol:** colaborador técnico.  
**Necesita:** operar la plataforma, actualizar contenedores, gestionar el clúster y revisar errores de captura/sondeo.  
**Veto:** sobrecarga de recursos o dependencias difíciles de mantener.

## Pains hipotéticos

- Inventario de activos desactualizado.
- Dificultad para relacionar cambios de IP/MAC, puertos o servicios con una marca temporal.
- Ausencia de un registro simple de variaciones de tráfico.
- Recolección y visualización dispersa entre scripts y herramientas.

## Triggers

- Auditoría o revisión de inventario.
- Red de laboratorio que crece o cambia.
- Necesidad de demostrar un cambio observable durante una prueba de seguridad.
- Necesidad de centralizar métricas y alertas básicas.

## Objeciones probables

- “Ya tenemos Zabbix/LibreNMS/Nagios”.
- “Grafana y Prometheus ya resuelven nuestros dashboards”.
- “No quiero que un sensor necesite privilegios de administrador”.
- “Sin acceso autenticado no me puedes decir exactamente qué SO o software corre”.
- “Kubernetes agrega complejidad para una red pequeña”.
- “No necesito otro producto; con un script basta”.

## Criterios de calificación

1. La organización controla legal y técnicamente la red.
2. Tiene necesidad explícita de inventario y trazabilidad de eventos.
3. Acepta límites de descubrimiento por red.
4. Puede operar o está dispuesta a evaluar Kubernetes.
5. Tiene un criterio para decidir si Sentinel aporta más que las herramientas actuales.

## Fuera del ICP

- Redes públicas o rangos de terceros sin autorización.
- Organizaciones que requieren respuesta automática, contención o remediación.
- Entornos que exigen inventario exhaustivo de software instalado o vulnerabilidades por endpoint.
- Redes de producción donde no se autorice captura/sondeo o no exista una fuente de tráfico.
- Organizaciones que necesitan un SIEM/NDR de nivel empresarial como reemplazo de sus plataformas actuales.

## Unknowns

Disposición a pagar, sectores, geografía inicial, madurez Kubernetes real, volumen de tráfico, número de redes/sensores, retención, canales de alerta y precisión mínima exigida.
