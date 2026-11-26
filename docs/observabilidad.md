# Runbook de observabilidad — Comparador de Precios (B1)

Este documento es el runbook operativo de la ampliación B1. Explica cómo se
exporta la telemetría, qué muestra el tablero, cómo se calcula el SLO, qué
significan las alertas, cómo diagnosticar una degradación, cómo ejecutar el
simulacro `EC-11`, qué muestreo y retención aplican y cómo degradar o revertir
la observabilidad sin afectar la API.

> [!IMPORTANT]
> **Estado de validación.** Los artefactos están versionados y el validador
> local comprueba su estructura, pero **la exportación real, los nombres de
> métricas y el disparo de la alerta no están certificados por este documento**.
> Esa certificación corresponde a **T-126**. Aquí no se afirma que la alerta ya
> se haya disparado ni que las consultas estén verificadas contra un colector.
> Tampoco se incluyen credenciales, endpoints privados ni datos personales.

## Contenido

1. [Arquitectura y fuentes de verdad](#1-arquitectura-y-fuentes-de-verdad)
2. [Tablero](#2-tablero)
3. [SLO y presupuesto de error](#3-slo-y-presupuesto-de-error)
4. [Alerta: qué significa y cómo responder](#4-alerta-qué-significa-y-cómo-responder)
5. [Diagnóstico](#5-diagnóstico)
6. [Simulacro EC-11](#6-simulacro-ec-11)
7. [Muestreo y retención](#7-muestreo-y-retención)
8. [Degradación y reversión](#8-degradación-y-reversión)

---

## 1. Arquitectura y fuentes de verdad

El backend instrumenta los flujos de registro de reportes y de comparación de
precios con OpenTelemetry. Las trazas y las métricas se exportan por OTLP/HTTP;
los logs de aplicación se emiten por `stdout` con `trace_id` y `span_id` para
correlacionarlos con las trazas.

```text
Backend FastAPI + OpenTelemetry SDK
  ├── trazas    → OTLP/HTTP <endpoint>/v1/traces
  ├── métricas  → OTLP/HTTP <endpoint>/v1/metrics
  └── logs      → stdout con trace_id/span_id
                  (el SDK configura además un LoggerProvider OTLP;
                   la recolección efectiva depende de la plataforma)

                         │
                         ▼
       Grafana Cloud o colector OTLP compatible
                         │
        ┌────────────────┼─────────────────┐
        ▼                ▼                 ▼
  Mimir/Prometheus     Tempo         Loki o logs de stdout
  (métricas y SLO)   (trazas)        (según la plataforma)
        └────────────────┴─────────────────┘
                         ▼
                      Grafana
          (tablero, reglas de alerta, notificación)
```

`OTEL_EXPORTER_OTLP_ENDPOINT` es una **URL base**: la aplicación agrega la ruta
de cada señal (`/v1/traces`, `/v1/metrics` y `/v1/logs`). No se versiona aquí
ningún endpoint real ni ninguna credencial.

### Fuentes de verdad

| Fuente | Qué gobierna |
|---|---|
| [`backend/app/config.py`](../backend/app/config.py) | Nombres, valores por defecto y tipos de todas las variables de entorno. |
| [`backend/app/compartido/telemetria.py`](../backend/app/compartido/telemetria.py) | Inicialización de trazas, métricas y logs; sanitización de atributos; política de muestreo errores-primero. |
| [`backend/app/compartido/logging_cfg.py`](../backend/app/compartido/logging_cfg.py) | Formato de logs, correlación por `trace_id`/`span_id` y redacción de datos sensibles. |
| [`infra/observabilidad/grafana/dashboards/observabilidad-comparador.json`](../infra/observabilidad/grafana/dashboards/observabilidad-comparador.json) | Paneles y consultas PromQL del tablero. |
| [`infra/observabilidad/grafana/alertas/slo-comparador.yml`](../infra/observabilidad/grafana/alertas/slo-comparador.yml) | Regla de grabación del SLI y alertas de SLO/presupuesto. |
| [`infra/observabilidad/grafana/provisioning/dashboards.yml`](../infra/observabilidad/grafana/provisioning/dashboards.yml) | Provider que carga el tablero en Grafana. |
| [`infra/observabilidad/README.md`](../infra/observabilidad/README.md) | Contenido de los artefactos, importación del tablero, carga de reglas y límites de validación. |
| [`scripts/validar_observabilidad.py`](../scripts/validar_observabilidad.py) | Validación local y de CI de ambos artefactos y detección de secretos. |
| [`infra/k6/ec11_latencia.js`](../infra/k6/ec11_latencia.js) | Escenario de carga del simulacro `EC-11`. |
| [`docs/adr/0020-observabilidad-opentelemetry-slo.md`](adr/0020-observabilidad-opentelemetry-slo.md) | Decisión arquitectónica y consecuencias de B1. |
| [`docs/despliegue.md`](despliegue.md) | Configuración de producción y variables del backend. |
| [`docs/PREGUNTAS_ABIERTAS.md`](PREGUNTAS_ABIERTAS.md) | `PA-05`: proveedor, cuotas y retención definitivos, aún `POR CONFIRMAR`. |

### Variables que gobiernan la observabilidad

| Variable | Valor por defecto | Efecto real |
|---|---|---|
| `ENTORNO` | `local` | Se publica como recurso OTel `deployment.environment`. Además, el valor exacto `production` (sin espacios y en minúsculas) desactiva la latencia simulada. |
| `OTEL_SDK_DISABLED` | `false` | Con `true` no se inicializa ningún provider ni exportador. La API sigue operando. |
| `OTEL_SERVICE_NAME` | `comparador-precios-backend` | Valor del recurso `service.name` y de la etiqueta `service_name` que usan el tablero y las reglas. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | vacío | URL base del colector OTLP/HTTP. Si está vacía, la telemetría queda inactiva sin error. |
| `OTEL_EXPORTER_OTLP_HEADERS` | vacío | Cabeceras OTLP en formato `clave=valor,clave2=valor2`. El valor de `Authorization` es un **secreto** y vive fuera del repositorio. |
| `OTEL_TRACES_SAMPLER` | `parentbased_traceidratio` | Estrategia declarada para trazas. La inicialización operativa crea los spans con `ALWAYS_ON` y delega la exportación en el procesador errores-primero; las variantes de `resolver_sampler` solo se ejercitan en pruebas. La palanca real de éxitos es `OTEL_TRACES_SAMPLER_ARG`. |
| `OTEL_TRACES_SAMPLER_ARG` | `0.2` | Proporción de trazas exitosas que se exportan. Los errores se exportan al 100 %. |
| `OTEL_METRICS_EXPORTER` | `otlp` | Con `otlp` se exportan métricas; cualquier otro valor deja el lector de métricas vacío. |
| `OTEL_LOGS_EXPORTER` | `otlp` | Con `otlp` el SDK configura el exportador OTLP de logs. La recolección efectiva de los logs de aplicación depende del puente de `logging` y de la plataforma. |
| `SIMULAR_LATENCIA_MS` | `0` | Milisegundos de espera artificial para `EC-11`. Solo aplica fuera de producción y con valor mayor que cero. En producción debe permanecer en `0`. |

La guía de despliegue reproduce esta tabla para el entorno productivo y explica
cómo configurar los secretos: [`docs/despliegue.md`](despliegue.md).

---

## 2. Tablero

El tablero versionado tiene UID `comparador-observabilidad` y título
`Comparador de Precios — Observabilidad`. Se aprovisiona desde
[`dashboards.yml`](../infra/observabilidad/grafana/provisioning/dashboards.yml)
con `allowUiUpdates: false`, `disableDeletion: true` y una relectura cada 30 s.
El JSON no fija el UID del datasource: todas las consultas usan la variable
`datasource`, que debe apuntar a la fuente Prometheus/Mimir que recibe las
métricas del colector.

Abre el tablero con:

```text
<GRAFANA_URL>/d/comparador-observabilidad
```

Sustituye `<GRAFANA_URL>` por la URL del stack. No se versiona una URL privada.

### Paneles

| Panel | Qué muestra | Consulta principal |
|---|---|---|
| Solicitudes por ruta | Tasa de peticiones por `http_target`. | `sum by (http_target) (rate(http_server_duration_milliseconds_count{...}[$__rate_interval]))` |
| Latencia de comparación p50/p95/p99 | Percentiles del histograma HTTP para la ruta de comparación; línea roja de referencia en 2 s. | `histogram_quantile(0.95, sum by (le) (rate(http_server_duration_milliseconds_bucket{...}[$__rate_interval]))) / 1000` |
| Tasa de errores 5xx | Proporción de respuestas 5xx sobre el total. | `sum(rate(...{http_status_code=~"5.."}[...])) / sum(rate(...[...]))` |
| Cache hit ratio | Proporción de comparaciones servidas desde caché. | `precios_comparaciones_total{cache_hit="true"}` dividido por el total. |
| Latencia de base de datos p95 | p95 de `precios.db_ms`, separado por `cache_hit`. | `histogram_quantile(0.95, sum by (le, cache_hit) (rate(precios_db_ms_bucket{...}[...]))) / 1000` |
| Reportes por estado | Tasa de reportes por `estado` (`aceptado`, `dudoso`, `otro`). | `sum by (estado) (rate(precios_reportes_total{...}[...]))` |
| Estado de alertas | Series `ALERTS` de las reglas `Comparador.*`. | `ALERTS{alertname=~"Comparador.*"}` |
| SLI de comparación (7 días) | Proporción de comparaciones que cumplen latencia ≤ 2 s y no son 5xx. | Consulta del SLI descrita en la [sección 3](#3-slo-y-presupuesto-de-error). |
| Presupuesto de error consumido (7 días) | Porcentaje del presupuesto del 1 % ya consumido; umbrales en 0,75 y 1. | `clamp_min(1 - SLI, 0) / 0.01`. |
| Cómo leer el SLO | Texto de ayuda con la definición y las advertencias. | — |

El rango por defecto del tablero es de **6 horas**, pero el SLI y el presupuesto
usan siempre una ventana fija de **7 días**, independiente de ese selector.
Todas las consultas de aplicación filtran por
`service_name="comparador-precios-backend"`; la consulta de `ALERTS` no lleva
ese filtro porque la serie la genera el motor de alertas.

### Cómo importarlo o aprovisionarlo

Los pasos completos están en
[`infra/observabilidad/README.md`](../infra/observabilidad/README.md#cómo-cargar-el-tablero).
En resumen: importa el JSON manualmente y elige el datasource Prometheus, o
monta el JSON y el YAML de provisioning en las rutas de Grafana. No se duplican
aquí los pasos de copia ni de recarga del provider.

### Nombres de métricas: esperados, no verificados

Las consultas asumen la traducción estándar de OTel a Prometheus: puntos por
guiones bajos, contadores con sufijo `_total` e histogramas con `_bucket`,
`_sum` y `_count`. **Estos nombres son esperados y deben confirmarse en T-126.**

| Métrica Prometheus esperada | Origen OTel | Uso |
|---|---|---|
| `http_server_duration_milliseconds_bucket` (y `_count`) | `http.server.duration` | Tráfico, latencia y SLI. |
| `precios_db_ms_bucket` (y `_sum`, `_count`) | `precios.db_ms` | Latencia de base de datos. |
| `precios_comparaciones_total` | `precios.comparaciones` | Cache hit ratio. |
| `precios_reportes_total` | `precios.reportes` | Reportes por estado. |
| `ALERTS` | Serie del motor de Prometheus/Mimir | Estado de las alertas. |

Advertencias:

- La etiqueta `http_target` es la **ruta plantilla** de baja cardinalidad
  (`/v1/productos/{id}/comparacion`), no la URL con el UUID. Si la
  instrumentación cambia a las convenciones semánticas nuevas, la etiqueta
  puede llamarse `http_route` y el histograma
  `http_server_request_duration_seconds_bucket`; en ese caso se ajustan las
  consultas sin cambiar el diseño de los paneles.
- El nombre `precios_db_ms_bucket` podría aparecer como
  `precios_db_ms_milliseconds_bucket` según el traductor OTel→Prometheus.
- `ALERTS` solo existe cuando el motor evalúa las reglas. El panel queda vacío
  hasta que `slo-comparador.yml` esté cargado y haya tráfico.
- Si los nombres reales difieren, se corrigen las consultas del JSON y del YAML
  en T-126. El diseño del tablero no cambia.

---

## 3. SLO y presupuesto de error

### Definición

- **SLI**: proporción de peticiones a
  `GET /v1/productos/{id}/comparacion` que terminan en **≤ 2 s** y **sin
  respuesta 5xx**.
- **SLO**: **99,0 %** de cumplimiento en una ventana móvil de **7 días**.
- **Presupuesto de error**: **1,0 %** de las peticiones de comparación en esos
  7 días.
- **Consumo del presupuesto**: `max(1 - SLI, 0) / 0.01`. Al **75 %** se emite
  una advertencia; al **100 %** el presupuesto está agotado y el SLO está
  incumplido.

La consulta del SLI usa la etiqueta `http_target` con el valor
`/v1/productos/{id}/comparacion`. No usa la URL concreta porque cada UUID
crearía una serie distinta de altísima cardinalidad; la ruta plantilla agrupa
todas las comparaciones y es la misma que exporta la instrumentación ASGI.

### Fórmula e interpolación

El histograma HTTP no tiene un bucket exacto en 2000 ms. Sus límites por
defecto incluyen 1000 ms y 2500 ms, así que el SLI interpola linealmente la
fracción de peticiones de hasta 2 s:

```text
numerador = rate(bucket_le_1000_sin_5xx)
          + (2000 - 1000) / (2500 - 1000)
          * (rate(bucket_le_2500_sin_5xx) - rate(bucket_le_1000_sin_5xx))

SLI = numerador / rate(count_total_comparaciones)
```

El numerador excluye las respuestas 5xx con `http_status_code!~"5.."`; el
denominador incluye todas las comparaciones, de modo que un 5xx cuenta como
incumplimiento. La interpolación supone distribución uniforme dentro del bucket
de 1000–2500 ms, la misma aproximación que usa `histogram_quantile`. **No es un
conteo exacto de peticiones de 2 s.**

### Regla y alertas

| Regla | Tipo | Expresión | `for` | Severidad |
|---|---|---|---|---|
| `comparador:sli_comparacion_7d` | Grabación | La misma consulta del panel «SLI de comparación (7 días)». | — | — |
| `ComparadorSLOComparacionIncumplido` | Alerta | `comparador:sli_comparacion_7d < 0.99` | 5m | `critical` |
| `ComparadorPresupuestoErrorAlto` | Alerta | `clamp_min(1 - comparador:sli_comparacion_7d, 0) / 0.01 > 0.75` | 10m | `warning` |

La alerta crítica se dispara cuando el SLI cae por debajo de 0,99, es decir,
cuando el presupuesto de error supera el 100 %. La advertencia se dispara con
más del 75 % del presupuesto consumido (SLI por debajo de 0,9925). Ambas llevan
la etiqueta `service: comparador-precios-backend` y el `runbook_url` apunta a
este documento.

### Sin datos no es incumplimiento

Sin tráfico en la ventana, las consultas devuelven `NaN` y los paneles quedan
sin datos. Una expresión `NaN < 0.99` no produce una serie verdadera, por lo
que la alerta **no debe interpretarse como SLO incumplido**. Antes de declarar
un incidente, confirma que el denominador tiene tráfico y que el datasource
responde. Si el panel está vacío por un problema de recolección, el incidente
es de observabilidad, no de SLO.

### Límites de la ventana de 7 días

La ventana es fija de 7 días. Una carga de 3 minutos puede no bastar para llevar
el SLI por debajo de 0,99 si hay mucho tráfico previo. T-126 debe verificar la
magnitud real, ajustar la carga o la duración si hace falta y guardar la
evidencia. No se afirma en este documento que la alerta ya se haya disparado.

---

## 4. Alerta: qué significa y cómo responder

| Alerta | Severidad | `for` | Qué significa |
|---|---|---|---|
| `ComparadorSLOComparacionIncumplido` | `critical` | 5m | El SLI de comparación a 7 días está por debajo de 0,99; el presupuesto de error está agotado. |
| `ComparadorPresupuestoErrorAlto` | `warning` | 10m | Se consumió más del 75 % del presupuesto de error de 7 días; queda menos del 25 %. |

Ambas reglas están versionadas en
[`slo-comparador.yml`](../infra/observabilidad/grafana/alertas/slo-comparador.yml),
pero **no se afirma que ya se hayan disparado ni que estén cargadas en un
motor**. La carga inicial con `mimirtool` o `promtool` y la configuración de
contact points están descritas en
[`infra/observabilidad/README.md`](../infra/observabilidad/README.md#cómo-cargar-las-reglas-de-slo-y-alertas);
la notificación vive fuera del repositorio. La certificación real corresponde a
T-126.

### Primeros 15 minutos

1. **0–2 min: confirma el estado y el tráfico.** Revisa el panel «Estado de
   alertas» o consulta `ALERTS{alertname=~"Comparador.*"}`. Comprueba si la
   alerta está en `pending` (aún no se cumple el `for`) o `firing`, y si el
   denominador del SLI tiene tráfico. Si no hay datos, trata el caso como fallo
   de recolección antes de declarar un incumplimiento.
2. **2–5 min: triage en el tablero.** Mira «Solicitudes por ruta», «Latencia de
   comparación p50/p95/p99» y «Tasa de errores 5xx». Decide si el problema es
   latencia, errores o ambos, y si coincide con un despliegue, un cambio de
   configuración o el simulacro `EC-11`.
3. **5–10 min: abre una traza lenta o errónea.** En Grafana ve a **Explore →
   Tempo**, filtra por `service.name = comparador-precios-backend` y por la
   ruta de comparación; ordena por duración o filtra `duration > 2s` / estado
   de error. Copia el `trace_id`. El span `precios.obtener_comparacion` aporta
   `precios.cache_hit`, `precios.resultados_count` y `precios.db_ms`.
4. **10–15 min: revisa dependencias y decide mitigación.** Compara
   «Latencia de base de datos p95» y «Cache hit ratio». Comprueba
   `GET /v1/salud` y `GET /v1/salud/listo` para descartar problemas de BD o
   Redis, y revisa el span de comparación. Si el incidente coincide con un
   despliegue, valora revertirlo; si
   estás en un entorno de pruebas, confirma que `SIMULAR_LATENCIA_MS` es el
   esperado y vuelve a `0` al terminar. No desactives la telemetría como primera
   medida: perderías la evidencia. Si el SLO sigue incumplido o el presupuesto
   supera el 100 %, escala y abre el registro de incidente.
5. **Cierre:** guarda el `trace_id`, la ventana consultada, el panel y la acción
   tomada. T-126 usará esa evidencia para el informe de `EC-11`.

### Enlaces operativos

Sustituye `<GRAFANA_URL>` por la URL del stack:

- **Tablero:** `<GRAFANA_URL>/d/comparador-observabilidad`
- **Trazas:** `<GRAFANA_URL>/explore` → datasource Tempo → búsqueda por
  `trace_id` o por latencia.
- **Logs:** `<GRAFANA_URL>/explore` → datasource Loki (si está configurado) o
  la vista de logs de `stdout` del proveedor → búsqueda por `trace_id`.

La traza y los logs se correlacionan por el mismo `trace_id`. El log de acceso
`app.acceso` incluye además `X-Request-ID`, que sirve para seguir una petición
concreta aunque no se haya muestreado su traza. Si el `trace_id` está vacío en
una línea, esa línea se emitió fuera de un span válido; no es un fallo por sí
mismo.

> [!NOTE]
> La alerta solo puede evaluarse cuando las reglas están cargadas en
> Prometheus/Mimir y el datasource del tablero las consulta. La certificación de
> que se dispara en **≤ 5 minutos** con la carga de `EC-11` es T-126. Este
> runbook describe qué hacer cuando ocurra, no afirma que ya haya ocurrido.

---

## 5. Diagnóstico

### Localizar una traza

- **Por `trace_id`:** copia el valor de una línea de log (`trace_id=...`) y
  búscalo en Explore/Tempo. Es la ruta más rápida desde un error concreto.
- **Por latencia:** en Explore/Tempo filtra por
  `service.name = comparador-precios-backend` y por el span
  `precios.obtener_comparacion`; ordena por duración descendente. En el
  tablero, el panel p95/p99 te dice en qué franja horaria mirar.
- **Por ruta HTTP:** el span de servidor de FastAPI usa la ruta plantilla como
  `http_target` (o `http_route` si se activan las convenciones nuevas). No
  busques por el UUID concreto: la etiqueta de baja cardinalidad es la que
  agrupa las peticiones.
- **Muestreo:** los errores se exportan siempre y los éxitos al 20 % por
  defecto. Si una petición exitosa no tiene traza, puede ser muestreo, no un
  fallo. Las métricas HTTP no se muestrean, así que el SLI y los paneles de
  latencia no pierden precisión por este muestreo.

### Leer los logs

El formato de correlación es:

```text
<fecha> <nivel> <logger> [trace_id=<id> span_id=<id>] <mensaje>
```

El logger `app.acceso` registra método, URL redactada, código de estado,
duración, `X-Request-ID`, `trace_id` y `span_id`. El filtro
`FiltroPrivacidadLey1581` redacta correos (incluidos los percent-encoded),
coordenadas, tokens de autorización, direcciones IPv4, loopback IPv6 y huellas
de red; también redacta los tracebacks. La sanitización de spans elimina las
claves prohibidas y los cuerpos antes de exportar.

**Qué no aparece en la telemetría:**

- Coordenadas `lat`, `lng`, `latitude` o `longitude`.
- `reportante_id`, alias, correo electrónico o cualquier identidad.
- Direcciones IP, `huella_red` o la foto de prueba y su ruta
  (`foto_prueba_path`); solo se registra el booleano `precios.tiene_foto`.
- Cabeceras `Authorization`, cookies, contraseñas, tokens o secretos.
- Cuerpos de solicitud o respuesta (`*.body`).

Los logs de aplicación se emiten por `stdout`. El SDK configura un
`LoggerProvider` OTLP cuando `OTEL_LOGS_EXPORTER=otlp`, pero el puente
automático desde `logging` de la biblioteca estándar no forma parte de las
dependencias actuales; la recolección efectiva (stdout del proveedor, Loki u
otra) debe confirmarse en T-126. Mientras tanto, busca los logs en la salida del
servicio y correlaciona por `trace_id`.

### Consultar métricas

Ejemplos de PromQL para el datasource Prometheus/Mimir (ajusta la ventana si
necesitas más contexto):

```promql
# Tasa de solicitudes por ruta
sum by (http_target) (
  rate(http_server_duration_milliseconds_count{service_name="comparador-precios-backend"}[5m])
)

# p95 de comparación en segundos
histogram_quantile(0.95,
  sum by (le) (
    rate(http_server_duration_milliseconds_bucket{
      service_name="comparador-precios-backend",
      http_target="/v1/productos/{id}/comparacion"
    }[5m])
  )
) / 1000

# Proporción de 5xx
sum(rate(http_server_duration_milliseconds_count{
  service_name="comparador-precios-backend",
  http_status_code=~"5.."
}[5m]))
/
sum(rate(http_server_duration_milliseconds_count{
  service_name="comparador-precios-backend"
}[5m]))

# Estado de las alertas
ALERTS{alertname=~"Comparador.*"}
```

Para el SLI y el presupuesto usa el panel o la regla de grabación; no
repliques la consulta larga a mano salvo que estés depurando la propia regla.

### Comandos útiles

```bash
# Validar los artefactos versionados (sin red ni credenciales)
python3 scripts/validar_observabilidad.py

# Si el Python del sistema no tiene PyYAML, usa el entorno del backend
uv --directory backend run python ../scripts/validar_observabilidad.py

# Comprobar que la API responde
curl -sS http://127.0.0.1:8000/v1/salud

# Comprobar el contrato expuesto
curl -sS http://127.0.0.1:8000/openapi.json | head

# Ejercer una comparación (sustituye <uuid> por un producto real)
curl -sS "http://127.0.0.1:8000/v1/productos/<uuid>/comparacion?orden=precio_unitario"

# Pruebas de los artefactos de observabilidad
uv --directory backend run pytest tests/unitarias/test_observabilidad_artefactos.py -q
```

El validador comprueba el UID y los paneles mínimos del tablero, la variable
`datasource`, el uso de `http_target`, los buckets 1000/2500, la ventana `7d`,
la regla de grabación, las alertas y la ausencia de secretos. Sale con código 0
si todo está correcto y 1 si encuentra problemas.

Si el backend arranca con telemetría, el log debe incluir
`Telemetria OpenTelemetry inicializada`. Si `OTEL_EXPORTER_OTLP_ENDPOINT` está
vacío o `OTEL_SDK_DISABLED=true`, verás el mensaje correspondiente y la API
seguirá respondiendo.

---

## 6. Simulacro EC-11

El procedimiento completo, con la explicación del escenario k6 y del producto
de `setup()`, está en
[`infra/observabilidad/README.md`](../infra/observabilidad/README.md#simulacro-ec-11-latencia-controlada-y-k6).
Resumen operativo:

1. **Prepara el backend de pruebas.** Debe tener `ENTORNO=pruebas`,
   `SIMULAR_LATENCIA_MS=3000`, y `OTEL_EXPORTER_OTLP_ENDPOINT` con
   `OTEL_EXPORTER_OTLP_HEADERS` configurados. Sin endpoint, la API responde
   pero no hay datos nuevos en el tablero.
2. **Arranca el backend** y ejecuta el escenario desde otra terminal:

   ```bash
   k6 run infra/k6/ec11_latencia.js
   ```

   El guion resuelve un producto real con `GET /v1/productos?q=arroz&limite=1`
   y solo fija el threshold `http_req_failed: rate<0.01`; no tiene threshold de
   latencia porque el objetivo del simulacro es precisamente superar el SLO.
3. **Observa el tablero.** La latencia de comparación debe reflejar la espera y
   el SLI debe caer. La alerta `ComparadorSLOComparacionIncumplido` debería
   dispararse en **≤ 5 minutos** una vez cargadas las reglas, pero **la
   certificación real y la captura son T-126**.
4. **Ventana de 7 días.** Tres minutos de carga pueden no bastar para llevar el
   SLI por debajo de 0,99 si hay mucho tráfico previo. T-126 debe verificar la
   magnitud, ajustar carga o duración si hace falta y guardar la evidencia.
5. **Restablece la normalidad.** Detén el backend, pon `SIMULAR_LATENCIA_MS=0`
   y vuelve a arrancarlo. Verifica `/v1/salud`.

El guard de producción reconoce **exactamente** `ENTORNO=production`
(normalizado a minúsculas y sin espacios). Etiquetas como `prod` o `produccion`
no desactivan la espera; por eso el despliegue debe mantener
`SIMULAR_LATENCIA_MS=0` aunque el guard también proteja. Nunca ejecutes el
simulacro contra producción.

La evidencia de T-126 debe incluir: captura del tablero, estado de la alerta,
traza con el span responsable, salida de k6, ausencia de datos personales y
confirmación de que el p95 de comparación no se degradó por la instrumentación.

---

## 7. Muestreo y retención

### Muestreo de trazas

La política es **errores primero**:

- El SDK crea los spans con `ALWAYS_ON` para poder conocer su estado al
  cerrarlos.
- `ProcesadorErroresPrimero` exporta **el 100 % de los spans con estado
  `ERROR` o con un evento de excepción**.
- Los spans exitosos se exportan con probabilidad
  `OTEL_TRACES_SAMPLER_ARG` (**0,2 = 20 %** por defecto). La decisión se deriva
  del `trace_id`, de modo que todos los spans de una misma traza exitosa se
  conservan o se descartan juntos.
- `OTEL_TRACES_SAMPLER` declara la estrategia (`parentbased_traceidratio` por
  defecto), pero la inicialización operativa no llama a `resolver_sampler`:
  crea con `ALWAYS_ON` y aplica la política errores-primero. No cambies ese
  valor esperando modificar la exportación; la palanca real de los éxitos es
  `OTEL_TRACES_SAMPLER_ARG`.
- El ratio se acota entre 0 y 1. Un valor no finito se trata como 0.

Las **métricas no se muestrean**: todos los contadores e histogramas registran
todas las peticiones. Por eso el SLI, la latencia y los errores del tablero no
dependen del 20 % de trazas. El muestreo de trazas afecta al diagnóstico
detallado, no al cálculo del SLO.

### Retención

La retención la define el plan del proveedor (Grafana Cloud, colector o
plataforma equivalente), **no la aplicación**. Este repositorio no configura ni
declara periodos de retención. Cualquier cifra de la capa gratuita debe
marcarse como **por confirmar** y verificarse en la consola del proveedor
durante T-126.

`PA-05` sigue en estado `POR CONFIRMAR`: proveedor definitivo, cuotas,
retención y costo. Consulta
[`docs/PREGUNTAS_ABIERTAS.md`](PREGUNTAS_ABIERTAS.md) antes de asumir un límite.

### Coste y cuota

- El muestreo de éxitos reduce el volumen de trazas sin afectar el SLO.
- Si la cuota se acerca al límite, la palanca segura es reducir
  `OTEL_TRACES_SAMPLER_ARG` (por ejemplo, a 0,1) y confirmar la retención; no
  reduzcas la telemetría de errores.
- Un fallo o agotamiento del exportador no debe afectar la API; el SDK usa
  exportación por lotes y degradación silenciosa. Si el proveedor agota la
  cuota, la aplicación sigue funcionando y el tablero deja de recibir datos
  nuevos.

---

## 8. Degradación y reversión

| Situación | Efecto | Acción |
|---|---|---|
| El colector o el proveedor no responde | La API sigue respondiendo; los lotes fallan y se registran advertencias genéricas. | Verifica `/v1/salud`; corrige endpoint, red o credenciales. No reinicies la API por este motivo salvo que quieras limpiar el estado. |
| `OTEL_SDK_DISABLED=true` | No se inicializan trazas, métricas ni logs OTLP. La API funciona igual. | Es el interruptor de emergencia. Vuelve a `false` y reinicia para reactivar. |
| Endpoint o cabeceras retirados | La telemetría queda inactiva si el endpoint está vacío; si el endpoint existe pero la credencial es inválida, el exportador falla sin tumbar la API. | Retira el endpoint o las cabeceras del panel del proveedor, reinicia y verifica `/v1/salud`. Rota la credencial si pudo exponerse. |
| Latencia simulada activa | Solo en entornos distintos de `production`; añade espera a las rutas de negocio. | Pon `SIMULAR_LATENCIA_MS=0`, reinicia y verifica `/v1/salud`. En producción el guard ya la ignora. |
| Tablero o reglas incorrectos | El tablero muestra consultas vacías o las alertas no evalúan. | Restaura el commit anterior o desprovisiona el archivo; recarga Grafana/Prometheus. |
| Dashboard editado por error en la UI | No debería ocurrir: `allowUiUpdates: false` y `disableDeletion: true`. | Los cambios se hacen en el JSON versionado; restaura el archivo y recarga el provider. |

### Desactivar la telemetría sin tocar la API

1. Define `OTEL_SDK_DISABLED=true` en el panel de variables del proveedor.
2. Reinicia el servicio.
3. Verifica `GET /v1/salud` (HTTP 200) y que la aplicación siga respondiendo.
4. Para reactivar, vuelve a `false`, configura endpoint y cabeceras si hace
   falta, reinicia y confirma el log de inicialización.

### Revertir tablero y alertas

- **Tablero:** restaura la versión anterior de
  `infra/observabilidad/grafana/dashboards/observabilidad-comparador.json` y
  recarga Grafana. Si necesitas retirar el tablero, desprovisiona el provider;
  con `disableDeletion: true`, quitar el archivo no borra automáticamente el
  tablero ya cargado. El tablero es de solo lectura en la UI
  (`allowUiUpdates: false`); la fuente de verdad es el JSON versionado.
- **Reglas:** restaura el commit anterior de
  `infra/observabilidad/grafana/alertas/slo-comparador.yml` y vuelve a cargarlas
  con `mimirtool` o `promtool`. Si se desprovisionan, el panel «Estado de
  alertas» queda vacío, no en verde.
- **Notificaciones:** los contact points y las políticas viven fuera del
  repositorio; desactívalos en Grafana Cloud si la alerta genera ruido.

### Secretos

- `OTEL_EXPORTER_OTLP_HEADERS` es secreto. No se commitea, no se pega en
  incidencias y no se incluye en capturas.
- No se versionan URLs privadas del stack, tokens de escritura ni credenciales
  de Mimir/Prometheus.
- Si una credencial se expone, rótala en el proveedor y actualiza el secreto
  del despliegue; después reinicia el servicio.
- Las reglas y el tablero solo contienen etiquetas de baja cardinalidad y
  placeholders; el validador falla si detecta patrones de credenciales.

### Verificación final tras cualquier reversión

```bash
curl -sS http://127.0.0.1:8000/v1/salud
python3 scripts/validar_observabilidad.py
```

La API debe responder 200 y el validador debe terminar con código 0 (o con el
mensaje claro de PyYAML si usas el Python del sistema sin esa dependencia).
Recuerda que la validación real contra el colector, los nombres de métricas y
el disparo de la alerta es **T-126**.
