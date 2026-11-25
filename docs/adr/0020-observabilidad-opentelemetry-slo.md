# ADR-0020: Observabilidad con OpenTelemetry y SLO sobre EC-04 (EC-11)

## Estado

Propuesto — pendiente de aprobación del equipo antes de implementar.

## Contexto

La ampliación B1 exige instrumentar los flujos de registro y comparación con OpenTelemetry, disponer de métricas, trazas y registros correlacionados en un tablero, formalizar un SLO sobre `EC-04` con SLI y presupuesto de error, y tener al menos una alerta asociada (`EC-11`). El núcleo actual tiene logs JSON, `/v1/salud`, `/v1/salud/listo`, un script k6 para `EC-04` y CI, pero no tiene trazas distribuidas, métricas de aplicación, SLO ni alertas.

Fuerzas:

- Evidencia de operación real, no solo instalación de una herramienta.
- Localizar el componente responsable con trazas en ≤ 5 minutos.
- Presupuesto de costo cero y cuotas gratuitas.
- Privacidad estricta: nada de coordenadas, identidad, IP ni datos personales en telemetría.
- No degradar la disponibilidad ni la latencia de la API si el backend de observabilidad falla.
- Configuración como código y secretos fuera del repositorio.

## Alternativas consideradas

1. **Solo métricas nativas del proveedor (Railway/Render/Vercel):** es lo más simple, pero no ofrece trazas distribuidas ni correlación con logs; no alcanza para identificar el componente responsable de `EC-11`.
2. **Stack autohospedado (Grafana + Tempo + Loki + Mimir, o Prometheus + Jaeger):** da control total, pero exige contenedores, almacenamiento, operación y respaldo; choca con el entorno local sin Docker y con el presupuesto de costo cero.
3. **OpenTelemetry SDK + exportación OTLP a Grafana Cloud Free (o un endpoint OTLP equivalente):** instrumentación estándar y portable, trazas/métricas/logs en un solo backend, capa gratuita y configuración por variables de entorno. Es la alternativa elegida, con alternativa nativa si la cuota no alcanza.

## Decisión

Se adopta la alternativa 3:

- Instrumentar el backend con OpenTelemetry para los flujos `POST /v1/reportes` y `GET /v1/productos/{id}/comparacion`; los health checks se excluyen de trazas para evitar ruido.
- Exportar por OTLP/HTTP a Grafana Cloud Free (o al endpoint OTLP del proveedor) configurado con `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_SERVICE_NAME`, `OTEL_TRACES_SAMPLER_ARG` y `OTEL_SDK_DISABLED`. Las credenciales viven en variables de entorno/secretos, nunca en el repositorio.
- Correlacionar logs con `trace_id` y `span_id`; mantener el filtrado de coordenadas y datos personales.
- Definir el SLI de `EC-04` como la proporción de peticiones de comparación con latencia ≤ 2 s y sin error 5xx; SLO 99,0 % en ventana móvil de 7 días; presupuesto de error 1,0 %.
- Alertar cuando se incumpla el SLO o se consuma el presupuesto de error por encima del umbral definido; notificar al equipo y ensayar el simulacro de `EC-11`.
- Muestrear 100 % de errores y un porcentaje configurable de éxitos (20 % por defecto); documentar retención y costo.
- Inyectar latencia controlada solo en entornos de prueba mediante una variable explícita, deshabilitada en producción.
- Usar un exportador por lotes con timeout y degradación silenciosa; un fallo de observabilidad no debe afectar la API.
- Versionar el tablero y las reglas de alerta como código en `infra/observabilidad/`.

## Consecuencias

### Positivas

- Trazas, métricas y logs correlacionados en un tablero único.
- Diagnóstico rápido del componente responsable de una degradación.
- SLO y presupuesto de error explícitos, alineados con `EC-04`.
- Instrumentación estándar y portable; no se ata a un proveedor.
- Evidencia reproducible para `EC-11` y para el entregable de calidad.

### Negativas

- Dependencia de un backend externo y de su capa gratuita.
- Configuración adicional de credenciales, muestreo y retención.
- Riesgo de fuga de datos si no se sanitizan los atributos; se mitiga con lista de prohibidos y prueba automatizada.
- El tablero y las alertas requieren mantenimiento cuando cambian los nombres de métricas o rutas.

### Riesgos aceptados

- Si Grafana Cloud no está disponible o agota la cuota, se usa el endpoint OTLP nativo del proveedor o se reduce el muestreo; el SLO se mantiene con las métricas disponibles.
- La ventana de 7 días es una simplificación académica; en producción se ampliaría a 30 días.

## Verificación

- Simulacro `EC-11`: inyectar latencia, ejecutar k6, verificar alerta en ≤ 5 minutos y traza con el span responsable.
- Prueba de atributos prohibidos en trazas y logs (`lat`, `lng`, `reportante_id`, alias, correo, IP, `huella_red`, `foto_prueba_path`, `authorization`).
- Prueba con exportador caído: la API responde con normalidad.
- Verificación de que el tablero muestra SLI, meta, presupuesto de error y estado de alerta.
- Prueba de no degradación: el p95 de comparación no supera 2 s por la instrumentación.
- Validación en CI de la sintaxis del tablero y de las reglas de alerta.
