# Observabilidad del comparador de precios

Artefactos como código para operar el comparador con OpenTelemetry y Grafana.
El backend exporta métricas, trazas y logs por OTLP/HTTP; este directorio
versiona el tablero y su aprovisionamiento. **No contiene credenciales ni
endpoints reales.**

## Contenido

| Ruta | Propósito |
|---|---|
| `grafana/dashboards/observabilidad-comparador.json` | Tablero UID `comparador-observabilidad` con tráfico, latencia, errores, caché, base de datos, reportes, SLO y alertas. |
| `grafana/provisioning/dashboards.yml` | Provider de Grafana que carga los JSON del directorio `/var/lib/grafana/dashboards`. |
| `README.md` | Este documento: importación, métricas esperadas, SLO y límites de validación. |

## Cómo cargar el tablero

### Opción A: importación manual

1. En Grafana, abre **Dashboards → New → Import**.
2. Sube `observabilidad-comparador.json` o pega su contenido.
3. Cuando Grafana pida la fuente de datos, elige el datasource Prometheus que
   recibe las métricas del colector OTLP. También puedes elegirlo después con la
   variable **Datasource** del propio tablero.
4. Guarda el tablero. El JSON no fija ningún UID de datasource: todas las
   consultas usan la variable `${datasource}`.

### Opción B: aprovisionamiento

1. Copia o monta los JSON de `grafana/dashboards/` en
   `/var/lib/grafana/dashboards` del contenedor o host de Grafana.
2. Copia `grafana/provisioning/dashboards.yml` en
   `/etc/grafana/provisioning/dashboards/`.
3. Asegura que el usuario de Grafana puede leer ambos directorios.
4. El YAML de provisioning se lee al iniciar o recargar Grafana; el
   `updateIntervalSeconds: 30` del provider solo hace que Grafana vuelva a
   escanear los archivos de dashboards. Si cambias el YAML, recarga o reinicia
   Grafana.
5. Verifica en **Dashboards → Comparador de Precios** que el tablero
   `Comparador de Precios — Observabilidad` esté disponible.

Si tu despliegue usa otras rutas, ajusta `options.path` en el YAML. El provider
está configurado con `allowUiUpdates: false` y `disableDeletion: true`: los
cambios se hacen en el JSON versionado, no en la interfaz.

El proyecto no usa Docker en local; este aprovisionamiento aplica al entorno de
Grafana que se despliegue para B1. No requiere pasos manuales sobre el tablero.

## Métricas esperadas

Las consultas asumen la traducción estándar de OTel a Prometheus:
los puntos se convierten en guiones bajos, los contadores reciben el sufijo
`_total` y los histogramas exponen `_bucket`, `_sum` y `_count`. Las consultas de
métricas de la aplicación filtran por
`service_name="comparador-precios-backend"`; la consulta de `ALERTS` no lleva ese
filtro porque la serie la genera el motor de alertas.

> **Estos nombres son esperados, no verificados.** La validación contra el
> colector, Grafana Cloud/Mimir o el backend Prometheus real corresponde a
> **T-126**. Si el colector traduce los nombres de otra forma (por ejemplo, si
> añade o quita sufijos de unidad), se ajustan las consultas del JSON sin cambiar
> el diseño de los paneles.

| Métrica Prometheus esperada | Origen OTel | Tipo y unidad | Etiquetas esperadas | Paneles |
|---|---|---|---|---|
| `precios_comparaciones_total` | `precios.comparaciones` | Counter, `1` | `cache_hit`, `service_name` | Cache hit ratio |
| `precios_db_ms_bucket` (+ `_sum`, `_count`) | `precios.db_ms` | Histogram, `ms` | `le`, `cache_hit`, `service_name` | Latencia de base de datos p95 |
| `precios_reportes_total` | `precios.reportes` | Counter, `1` | `estado`, `idempotente`, `service_name` | Reportes por estado |
| `http_server_duration_milliseconds_bucket` (+ `_count`) | `http.server.duration` | Histogram, `ms` | `http_target`, `http_status_code`, `service_name` | Solicitudes, latencia, errores 5xx y SLO |
| `ALERTS` | Serie generada por el motor de alertas | Gauge | `alertname`, `alertstate` | Estado de alertas |

Notas sobre las etiquetas:

- `service_name` proviene del recurso OTel `service.name`. El colector puede
  añadir `job` e `instance`; el tablero no los usa.
- `estado` solo toma los valores de baja cardinalidad `aceptado`, `dudoso` y
  `otro`; la normalización la hace el backend antes de registrar la métrica.
- `cache_hit` toma `true` o `false`.
- `http_status_code` es el código HTTP (`200`, `500`, etc.).
- `http_target` es la ruta plantilla de baja cardinalidad que exporta la
  instrumentación ASGI actual (`route.path_format`), por ejemplo
  `/v1/productos/{id}/comparacion`; **no** es la URL concreta con el UUID. Las
  consultas HTTP del tablero usan esta etiqueta.
- `http_route` pertenece a las convenciones semánticas nuevas de HTTP y no está
  activada por defecto en la instrumentación instalada. Si se activa, se
  sustituye `http_target` por `http_route` en las consultas; el diseño de los
  paneles no cambia.
- `precios_db_ms` tiene unidad `ms`. El nombre esperado es
  `precios_db_ms_bucket`, pero algunos traductores podrían exponerlo como
  `precios_db_ms_milliseconds_bucket`; T-126 debe confirmar cuál aplica.
- Si la instrumentación usa las convenciones semánticas nuevas de HTTP, el
  histograma puede llamarse `http_server_request_duration_seconds_bucket` y sus
  etiquetas ser `http_route`, `http_response_status_code` y `url_path`. En ese
  caso se ajustan las consultas de latencia (sin división por 1000) y las
  constantes del SLI a 1 s y 2,5 s.
- `ALERTS` solo existe cuando el motor de Prometheus o Mimir evalúa reglas de
  alerta. El panel está preparado para `ALERTS{alertname=~"Comparador.*"}` y
  quedará vacío hasta que **T-122** cargue las reglas.

## Definición del SLI y del SLO

- **SLI**: proporción de peticiones a
  `GET /v1/productos/{id}/comparacion` que cumplen las dos condiciones:
  latencia menor o igual a **2 s** y respuesta sin error **5xx**.
- **SLO**: **99,0 %** de cumplimiento en una ventana móvil de **7 días**.
- **Presupuesto de error**: **1,0 %** de las peticiones de comparación en esos
  7 días.
- **Consumo del presupuesto**:
  `max(1 - SLI, 0) / 0.01`. Al 100 % el presupuesto está agotado; por encima de
  100 % el SLO está incumplido.

La consulta del panel usa los buckets `le="1000"` y `le="2500"` del histograma en
milisegundos y excluye `http_status_code!~"5.."` del numerador. El denominador es
el total de comparaciones. La ventana del SLI es fija de 7 días, independiente
del rango de 6 horas que muestra el tablero por defecto.

El histograma HTTP por defecto del SDK de OpenTelemetry no tiene un límite
exacto en 2000 ms: sus límites son `... 750, 1000, 2500, 5000 ...` (o los
equivalentes en segundos si se usan las convenciones semánticas nuevas). Por eso
el SLI estima la fracción de peticiones de hasta 2 s interpolando linealmente
entre los buckets de 1000 ms y 2500 ms, con la misma suposición de distribución
uniforme que usa `histogram_quantile`. Es una aproximación, no un conteo exacto.
Si T-126 confirma otros límites de bucket, se ajustan las constantes de la
consulta o se añade un bucket explícito de 2 s en la instrumentación.

Advertencias de interpretación:

- `histogram_quantile` es una aproximación basada en los límites de bucket del
  histograma; no es un percentil exacto.
- La estimación del SLI depende de que existan los buckets de 1000 ms y 2500 ms.
  Si el colector usa otros límites, la consulta devuelve `NaN` hasta ajustarla
  en T-126.
- Sin tráfico en la ventana, las consultas devuelven `NaN` y los paneles quedan
  sin datos; no debe interpretarse como SLO incumplido.
- Los umbrales gráficos (rojo por debajo de 0,99, línea de 2 s) son ayudas
  visuales; la fuente de verdad es la consulta PromQL y la regla de alerta de
  T-122.

## Validación

Validación local del JSON, sin conexión a Grafana:

```bash
python3 -m json.tool infra/observabilidad/grafana/dashboards/observabilidad-comparador.json > /dev/null
```

Si tienes `jq`, puedes comprobar además los campos principales:

```bash
jq -e '.uid == "comparador-observabilidad" and (.panels | length > 0)' \
  infra/observabilidad/grafana/dashboards/observabilidad-comparador.json
```

La validación real contra Grafana, el colector OTLP y la traducción de nombres a
Prometheus corresponde a **T-126**. Este repositorio no incluye credenciales de
Grafana ni un colector, por lo que no se ejecutan consultas contra un backend
real en esta tarea.

## Seguridad

- No se commitean tokens, usuarios, contraseñas ni cabeceras de autorización.
- El datasource se elige con la variable `datasource`; no se fija un UID.
- Las credenciales del colector (`OTEL_EXPORTER_OTLP_HEADERS`) viven en variables
  de entorno o en el gestor de secretos del despliegue, nunca en este directorio.
- Las consultas no incluyen coordenadas, identidad ni datos personales; solo
  etiquetas de baja cardinalidad.
