# Observabilidad del comparador de precios

Artefactos como código para operar el comparador con OpenTelemetry y Grafana.
El backend exporta métricas y trazas por OTLP/HTTP y emite logs de aplicación
correlacionados con `trace_id`/`span_id`; este directorio versiona el tablero,
las reglas de SLO y alertas, y su aprovisionamiento.
**No contiene credenciales ni endpoints reales.**

El procedimiento operativo de respuesta a alertas, diagnóstico, simulacro,
muestreo, retención y reversión está en el runbook
[`docs/observabilidad.md`](../../docs/observabilidad.md). Este README se limita
a los artefactos y a su carga; no duplica el runbook.

## Contenido

| Ruta | Propósito |
|---|---|
| `grafana/dashboards/observabilidad-comparador.json` | Tablero UID `comparador-observabilidad` con tráfico, latencia, errores, caché, base de datos, reportes, SLO y alertas. |
| `grafana/provisioning/dashboards.yml` | Provider de Grafana que carga los JSON del directorio `/var/lib/grafana/dashboards`. |
| `grafana/alertas/slo-comparador.yml` | Reglas Prometheus/Mimir: SLI grabado a 7 días, alerta de SLO y alerta de presupuesto de error. |
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

## Cómo cargar las reglas de SLO y alertas

`grafana/alertas/slo-comparador.yml` es un archivo de reglas compatible con
Prometheus y Mimir. Define la regla de grabación `comparador:sli_comparacion_7d`
y dos alertas:

| Regla | Tipo | Expresión | `for` | Severidad |
|---|---|---|---|---|
| `comparador:sli_comparacion_7d` | Grabación | La misma consulta del panel «SLI de comparación (7 días)» | — | — |
| `ComparadorSLOComparacionIncumplido` | Alerta | `comparador:sli_comparacion_7d < 0.99` | 5m | `critical` |
| `ComparadorPresupuestoErrorAlto` | Alerta | `clamp_min(1 - comparador:sli_comparacion_7d, 0) / 0.01 > 0.75` | 10m | `warning` |

**El archivo está versionado, pero no cargado en ningún motor desde este
repositorio.** La carga real y la validación de las consultas contra el colector
corresponden a **T-126**.

### Opción A: Mimir o Grafana Cloud

1. Configura `mimirtool` con la URL del tenant de Mimir y las credenciales que
   entregue tu gestor de secretos. No escribas tokens en el repositorio.
2. Carga las reglas (los valores entre `<>` son marcadores, no secretos):

   ```bash
   mimirtool rules load \
     --address="<URL_DE_MIMIR>" \
     --id="<TENANT_ID>" \
     --user="<USUARIO>" \
     --key="$MIMIR_API_KEY" \
     infra/observabilidad/grafana/alertas/slo-comparador.yml
   ```

3. Verifica con `mimirtool rules list`, usando las mismas opciones de conexión,
   que aparece el grupo `comparador-slo`.
4. La notificación se configura en Grafana Cloud mediante contact points y
   notification policies. Esa configuración vive fuera del repositorio y no se
   versiona aquí: el YAML solo contiene reglas y etiquetas.

### Opción B: Prometheus

1. Copia `slo-comparador.yml` al servidor de Prometheus.
2. Añade el archivo a `rule_files` en `prometheus.yml`.
3. Valida la sintaxis con `promtool check rules slo-comparador.yml` y recarga
   Prometheus.

La etiqueta `service` de las alertas es `comparador-precios-backend`. El enlace
`runbook_url` apunta a [`docs/observabilidad.md`](../../docs/observabilidad.md),
el runbook operativo de T-125.

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
  alerta. El panel está preparado para `ALERTS{alertname=~"Comparador.*"}`;
  las reglas están versionadas en `grafana/alertas/slo-comparador.yml` y
  quedarán vacías hasta que se carguen en el motor (T-126).

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

La regla de grabación `comparador:sli_comparacion_7d` reutiliza exactamente esa
consulta. La alerta `ComparadorSLOComparacionIncumplido` se dispara cuando el SLI
cae por debajo de 0,99 durante 5 minutos, y
`ComparadorPresupuestoErrorAlto` avisa cuando el consumo del presupuesto supera
el 75 % durante 10 minutos. Ambas viven en
`grafana/alertas/slo-comparador.yml` (T-122).

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
  visuales; la fuente de verdad es la consulta PromQL y la regla de grabación de
  `grafana/alertas/slo-comparador.yml`.

## Simulacro EC-11: latencia controlada y k6

El backend incluye `LatenciaSimuladaMiddleware`
(`backend/app/compartido/latencia_simulada.py`). La espera solo se aplica cuando
`ENTORNO` no es `production`, `SIMULAR_LATENCIA_MS` es mayor que cero y la ruta
pertenece a los prefijos de negocio configurados. Las rutas de salud
(`/v1/salud` y `/v1/salud/listo`) quedan fuera para no degradar las sondas.
Con el valor por defecto `SIMULAR_LATENCIA_MS=0` la API no cambia.

`infra/k6/ec11_latencia.js` genera la carga del simulacro: 200 VUs durante
3 minutos contra
`GET /v1/productos/{id}/comparacion?orden=precio_unitario`, con la etiqueta
`endpoint=comparacion` y una pausa de 1 s entre iteraciones. El guion fija solo
el threshold `http_req_failed: rate<0.01` y **ningún threshold de latencia**:
durante el simulacro se espera que la latencia supere el SLO, y un umbral de
latencia haría fallar k6 justo por el comportamiento buscado. En `setup()` se
resuelve un producto real con `GET /v1/productos?q=arroz&limite=1`; si no hay
resultados, el escenario falla con un error explícito en lugar de ejercer carga
contra un UUID inexistente.

### Procedimiento

1. Configura el backend de pruebas. Además de `ENTORNO=pruebas` y
   `SIMULAR_LATENCIA_MS=3000`, define `OTEL_EXPORTER_OTLP_ENDPOINT` y
   `OTEL_EXPORTER_OTLP_HEADERS` para que trazas y métricas lleguen al colector;
   sin esas variables la API responde, pero no habrá datos que observar en el
   tablero:

   ```bash
   ENTORNO=pruebas SIMULAR_LATENCIA_MS=3000 \
     OTEL_EXPORTER_OTLP_ENDPOINT="<endpoint-otlp>" \
     OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <credencial>" \
     uv --directory backend run uvicorn app.main:app --port 8000
   ```

2. Ejecuta el escenario de carga desde otra terminal:

   ```bash
   k6 run infra/k6/ec11_latencia.js
   ```

   Por defecto `setup()` busca un producto de arroz en el seed y usa su ID.
   `BASE_URL` (por defecto `http://127.0.0.1:8000`) y `PRODUCTO_ID` son
   opcionales:

   ```bash
   BASE_URL=http://127.0.0.1:8000 \
     PRODUCTO_ID=<uuid-real-del-seed> \
     k6 run infra/k6/ec11_latencia.js
   ```

   `3b241101-e2bb-4255-8caf-4136c566a962` es el UUID de ejemplo de los
   contratos, **no un ID fijo del seed**: `scripts/semilla.py` inserta los
   productos sin `id` y PostgreSQL genera UUIDs aleatorios. Solo si usas el
   override, confirma el ID real con
   `SELECT id, nombre FROM producto WHERE nombre = 'Arroz blanco tradicional';`.

3. Observa el tablero y el estado de la alerta. La alerta
   `ComparadorSLOComparacionIncumplido` debe dispararse en **≤ 5 minutos**.
   **La carga real, la alerta y su captura son parte de T-126**; esta tarea solo
   deja el mecanismo y el escenario listos. No se afirma aquí que la alerta ya
   se haya disparado.

   La ventana del SLO es de 7 días: 3 minutos de carga pueden no bastar para
   llevar el SLI por debajo de 0.99 si hay mucho tráfico previo. T-126 debe
   verificar la magnitud real y ajustar la carga o la duración si hace falta.

4. Verifica en la traza más lenta de
   `GET /v1/productos/{id}/comparacion` que la duración del span del servidor
   refleja la espera. El log de acceso `app.acceso` también muestra la duración
   con la latencia incluida.

5. Restablece la normalidad: detén el backend, pon `SIMULAR_LATENCIA_MS=0` y
   vuelve a arrancarlo.

6. En producción el middleware ignora la variable: `ENTORNO=production`
   (normalizado a minúsculas y sin espacios) es el valor que desactiva la
   simulación aunque `SIMULAR_LATENCIA_MS` sea positivo. Etiquetas como `prod` o
   `produccion` no la desactivan; mantén `SIMULAR_LATENCIA_MS=0` en el
   despliegue.

## Validación

La validación es local, determinista y no necesita red ni credenciales:

```bash
uv --directory backend run python ../scripts/validar_observabilidad.py
```

En CI se ejecuta con el entorno virtual de la raíz:

```bash
source .venv/bin/activate
python scripts/validar_observabilidad.py
```

El validador comprueba:

- El JSON del tablero: UID `comparador-observabilidad`, al menos 10 paneles de
  datos, títulos mínimos, variable `datasource`, uso de `http_target` (sin
  `http_route`), buckets `1000`/`2500`, ventana `7d` y ausencia de secretos.
- El YAML de reglas: `groups` no vacío, al menos una alerta, regla de grabación
  `comparador:sli_comparacion_7d` idéntica a la consulta del tablero, y cada
  alerta con `for`, `labels.severity` y `annotations.summary`/`description`.
- Ausencia de secretos en ambos archivos y de URLs de Grafana en las reglas.

Sale con código 0 si todo es correcto y 1 si encuentra problemas. Solo requiere
la biblioteca estándar y PyYAML; si PyYAML no está disponible, muestra un
mensaje claro. Los artefactos actuales pasan:

```bash
uv --directory backend run pytest tests/unitarias/test_observabilidad_artefactos.py -q
```

La validación real contra Grafana, el colector OTLP y la traducción de nombres a
Prometheus corresponde a **T-126**. Este repositorio no incluye credenciales de
Grafana ni un colector, por lo que no se ejecutan consultas contra un backend
real en esta tarea.

## Seguridad

- No se commitean tokens, usuarios, contraseñas ni cabeceras de autorización.
- El datasource se elige con la variable `datasource`; no se fija un UID.
- Las reglas de `grafana/alertas/slo-comparador.yml` no incluyen URLs de Grafana,
  webhooks ni credenciales. Los contact points de notificación se configuran en
  Grafana Cloud y sus secretos viven en el gestor de secretos del despliegue.
- `scripts/validar_observabilidad.py` falla si detecta patrones de
  `Authorization`, tokens, contraseñas o claves API en los artefactos.
- Las credenciales del colector (`OTEL_EXPORTER_OTLP_HEADERS`) viven en variables
  de entorno o en el gestor de secretos del despliegue, nunca en este directorio.
- Las consultas no incluyen coordenadas, identidad ni datos personales; solo
  etiquetas de baja cardinalidad.
