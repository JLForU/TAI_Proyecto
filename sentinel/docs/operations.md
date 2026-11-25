# Operación y Ground Truth (GT-01..GT-05)

## Acceso a la interfaz del operador
Acceder exclusivamente mediante reenvío de puertos local (`kubectl port-forward`), sin exponer servicios públicamente (`FR-GUI-07`).

## Escenarios de Ground Truth (`EN-06`)
- **GT-01**: operación normal con activos descubiertos, línea base inicial y sin alertas.
- **GT-02**: aparición de un host nuevo registrado en el inventario.
- **GT-03**: ausencia de un host tras el periodo/ciclos configurados.
- **GT-04**: tráfico elevado por encima del umbral tras la ventana inicial (`TrafficThresholdExceeded`, `R-01`).
- **GT-05**: indisponibilidad del sensor/colector (`SensorUnavailable`, `R-04`).

## Validación de rendimiento en laboratorio (`EN-07` — documented-only)
Los objetivos de latencia y rendimiento en laboratorio no son vinculantes y se documentan como referencia de prueba local/clúster sin bloquear el pipeline.
