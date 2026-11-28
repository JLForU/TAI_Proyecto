# Preguntas de clarificación — Arreglo del botón de reset (GUI)

Contexto: revisé el flujo actual y el camino feliz funciona en pruebas
(`POST /ui/reset` → `303` → `/ui/assets?reset=ok`, borrando los datos derivados).
No hay test que cubra el botón de la GUI. Para corregir el defecto real necesito
saber qué observas. Responde escribiendo la letra después de cada `[Answer]:`.

## Question 1
Al pulsar "Resetear escenario", ¿qué ocurre exactamente?

A) No pasa nada: no navega ni cambia la pantalla

B) Muestra una página de error (403/409/500/502); si recuerdas el texto o código, descríbelo en la opción Other

C) Redirige a Inventario con el banner de éxito, pero los datos siguen apareciendo

D) El botón no se ve, no se puede pulsar o aparece deshabilitado

E) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2
¿En qué entorno lo reproduces?

A) Local con venv/uvicorn (`python -m sentinel.core`)

B) Docker (docker run / docker compose)

C) Kubernetes con Helm

D) En varios / todos los anteriores

E) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3
¿Cuándo falla?

A) Siempre

B) Solo mientras hay un discovery en curso

C) De forma intermitente (a veces sí, a veces no)

D) No lo sé / no lo he comprobado

E) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 4
¿Qué debería hacer el botón?

A) Borrar los datos derivados y mostrar el banner de éxito (comportamiento esperado actual)

B) Además detener/cancelar un discovery en curso en lugar de rechazar el reset

C) Pedir una confirmación más clara y deshabilitar el botón mientras procesa

D) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 5
¿Qué alcance quieres para el arreglo?

A) Corregir el defecto y añadir tests (recomendado)

B) Solo corregir el defecto, sin tests nuevos

C) Corregir y además mejorar la UX (confirmación, estado de carga, banner)

D) Other (please describe after [Answer]: tag below)

[Answer]: 
