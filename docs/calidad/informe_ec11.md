# Informe EC-11 — Detección del incumplimiento del SLO de comparación

> **Estado: PENDIENTE DE EJECUCIÓN.**
> Este documento es la plantilla reproducible de la certificación `EC-11`.
> No contiene evidencia real todavía y **no certifica** el escenario. Se
> completará cuando existan el colector OTLP/Grafana, las credenciales y `k6`
> en el entorno de pruebas. No pegar tokens, endpoints privados ni datos
> personales en este archivo.

## 1. Objetivo

Demostrar que una degradación de latencia en `GET /v1/productos/{id}/comparacion`
que incumple el SLO (99 % de peticiones ≤ 2 s y sin 5xx en 7 días):

1. Dispara la alerta `ComparadorSLOComparacionIncumplido` en **≤ 5 minutos**.
2. La traza de una petición lenta identifica el componente responsable.
3. El tablero muestra el SLI y el presupuesto de error consumido.
4. La evidencia es reproducible y no contiene PII.
5. El p95 de comparación sin latencia inyectada no se degrada por la
   instrumentación.

## 2. Prerrequisitos

- [ ] Backend con `.env` y conexión a Supabase/Redis (para comparación real).
- [ ] Colector OTLP/HTTP y stack de Grafana Cloud (o equivalente) con métricas,
      trazas y logs.
- [ ] Variables: `OTEL_SDK_DISABLED=false`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
      `OTEL_EXPORTER_OTLP_HEADERS` (secreto), `OTEL_LOGS_EXPORTER=otlp`,
      `OTEL_TRACES_SAMPLER_ARG=0.2`.
- [ ] Tablero importado o aprovisionado y reglas de `slo-comparador.yml`
      cargadas en Prometheus/Mimir.
- [ ] `k6` instalado en la máquina que ejecutará la carga.
- [ ] Producto real del seed (el script `infra/k6/ec11_latencia.js` lo resuelve
      en `setup()`; `PRODUCTO_ID` es un override opcional).

## 3. Procedimiento

### 3.1 Línea base sin latencia inyectada

```bash
# Terminal 1
ENTORNO=pruebas SIMULAR_LATENCIA_MS=0 \
  uv --directory backend run uvicorn app.main:app --port 8000

# Terminal 2
k6 run infra/k6/ec11_latencia.js
```

Registrar: fecha UTC, p95/p99 de comparación en el tablero, tasa de 5xx,
`http_req_failed` de k6 y ausencia de alertas activas.

### 3.2 Simulacro con latencia inyectada

```bash
# Reiniciar el backend con latencia de 3 s
ENTORNO=pruebas SIMULAR_LATENCIA_MS=3000 \
  OTEL_SDK_DISABLED=false \
  OTEL_EXPORTER_OTLP_ENDPOINT="<endpoint-otlp>" \
  OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <credencial>" \
  OTEL_LOGS_EXPORTER=otlp \
  uv --directory backend run uvicorn app.main:app --port 8000

# En otra terminal
k6 run infra/k6/ec11_latencia.js
```

Durante el simulacro:

1. Anotar la hora UTC de inicio de la carga.
2. Vigilar el tablero (`SLI de comparacion (7 dias)` y presupuesto).
3. Anotar la hora UTC en que la alerta pasa a `firing`.
4. Abrir la traza más lenta y registrar el span/componente responsable
   (`service_name`, nombre del span, duración, `http_target`, estado).
5. Verificar que los logs de `app.*` correlacionan por `trace_id` y que no
   contienen correo, coordenadas, IP, `huella_red`, tokens ni cuerpos.
6. Al terminar, reiniciar con `SIMULAR_LATENCIA_MS=0` y confirmar que la
   latencia vuelve a la línea base.

> La ventana del SLO es de 7 días. Si el tráfico previo es alto, 3 minutos de
> latencia pueden no bastar para que el SLI caiga por debajo de 0,99. En ese
> caso, repetir la carga o extenderla, registrando la decisión. No se debe
> alterar el umbral del SLO para forzar el disparo.

## 4. Evidencia a adjuntar

| Evidencia | Enlace o captura | Fecha UTC | Responsable |
|---|---|---|---|
| Tablero con SLI y presupuesto durante el simulacro | pendiente | | |
| Alerta en estado `firing` y hora de inicio | pendiente | | |
| Traza lenta con componente responsable | pendiente | | |
| Logs correlacionados por `trace_id` (sin PII) | pendiente | | |
| Resultado de `k6` (resumen) | pendiente | | |
| Línea base de p95 antes/después | pendiente | | |
| Confirmación de `SIMULAR_LATENCIA_MS=0` al cierre | pendiente | | |

Los enlaces a Grafana pueden ser URLs privadas; si el repositorio es público,
guardar capturas redactadas o enlaces con acceso controlado, nunca credenciales.

## 5. Criterios de aceptación

- [ ] La alerta se dispara en **≤ 5 minutos** desde que el SLI cae bajo 0,99.
- [ ] La traza identifica el componente responsable de la latencia.
- [ ] El tablero muestra el SLI y el presupuesto consumido.
- [ ] La evidencia es reproducible con este procedimiento.
- [ ] **0 PII** en tablero, trazas y logs: sin correo, coordenadas, IP,
      `huella_red`, `reportante_id`, alias, foto ni cuerpos.
- [ ] El p95 de comparación sin latencia inyectada no se degrada respecto a la
      línea base.
- [ ] `SIMULAR_LATENCIA_MS=0` y el access log nativo desactivado al cierre.

## 6. Resultado

> Pendiente de ejecución. No declarar `EC-11` certificado hasta completar la
> tabla de evidencia y los criterios de aceptación.

- **Veredicto:** pendiente.
- **Desviaciones:** pendiente.
- **Acciones correctivas:** pendiente.
