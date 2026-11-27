# Guía Reproducible de Ejecución Local y Despliegue (`T-50`)

Esta guía describe paso a paso cómo ejecutar el núcleo `v1.0-nucleo` en entorno local (Windows / Linux / macOS) **sin Docker** mediante `uv` y Node.js, y cómo desplegarlo en producción sobre infraestructura de **costo cero** (Vercel, Render / Railway, Supabase, Upstash y GitHub Actions).

---

## Parte I — Ejecución Local Reproducible (sin Docker)

### 1. Prerrequisitos
- **Python 3.12+** y gestor de paquetes **`uv`**
- **Node.js 20+** y **`npm`**
- Acceso a un proyecto de **Supabase** (PostgreSQL + PostGIS + Auth + Storage) y una instancia Redis en **Upstash**

### 2. Variables de Entorno (`.env`)
Copia `.env.example` a `.env` en la raíz del repositorio y completa los valores del proyecto:

```ini
DATABASE_URL=postgresql+asyncpg://app_backend.<project-ref>:<PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
MIGRATIONS_DATABASE_URL=postgresql://postgres.<project-ref>:<PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
SUPABASE_JWT_SECRET=<jwt-secret>
REDIS_URL=rediss://default:<UPSTASH_TOKEN>@<endpoint>.upstash.io:6379
HUELLA_SECRETO_MAESTRO=<cadena-aleatoria-32-chars>
JOB_TOKEN=<token-jobs-internos-32-chars>
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
```

> [!IMPORTANT]
> En redes locales Windows sin enrutamiento IPv6 hacia Supabase, utiliza siempre la URL del **Session Pooler (puerto `5432`, host `*.pooler.supabase.com`)** para migraciones y desarrollo local. No subas el archivo `.env` al repositorio.

#### Variables de observabilidad (OpenTelemetry, B1)

Estas variables configuran la telemetría de la ampliación B1: trazas y métricas vía OTLP/HTTP, y logs de `app.*` que salen por `stdout` con `trace_id`/`span_id` y, con `OTEL_LOGS_EXPORTER=otlp`, también por OTLP. Los INFO de terceros se descartan; sus WARNING/ERROR salen por `stderr` redactados, y los logs de Uvicorn no se exportan por OTLP. El SDK se inicializa al arrancar la aplicación (`T-120`); si `OTEL_EXPORTER_OTLP_ENDPOINT` está vacío o `OTEL_SDK_DISABLED=true`, la API sigue operativa sin telemetría.

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `ENTORNO` | `local` | Entorno de ejecución (`local`, `pruebas`, `production`). Se publica como `deployment.environment` en la telemetría. |
| `OTEL_SDK_DISABLED` | `false` | Con `true` desactiva toda la telemetría y deja la API operativa. Es el interruptor de emergencia. |
| `OTEL_SERVICE_NAME` | `comparador-precios-backend` | Nombre del servicio que aparece en trazas y métricas, y valor de la etiqueta `service_name` que filtran el tablero y las reglas. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | vacío | URL base del colector OTLP/HTTP (Grafana Cloud o equivalente). La aplicación agrega `/v1/traces`, `/v1/metrics` y `/v1/logs`. Si está vacío, la telemetría queda inactiva. |
| `OTEL_EXPORTER_OTLP_HEADERS` | vacío | Cabeceras de autenticación en formato `clave=valor,clave2=valor2`, por ejemplo `Authorization=Basic <credencial>`. **Es un secreto**: configúralo en el panel del proveedor o en el gestor de secretos, nunca en el repositorio. |
| `OTEL_TRACES_SAMPLER` | `parentbased_traceidratio` | Estrategia declarada para trazas. La inicialización crea los spans con `ALWAYS_ON` y el procesador errores-primero decide la exportación; la palanca real de éxitos es `OTEL_TRACES_SAMPLER_ARG`. |
| `OTEL_TRACES_SAMPLER_ARG` | `0.2` | Proporción de trazas exitosas exportadas; los errores se exportan al 100 %. Las métricas no se muestrean. |
| `OTEL_METRICS_EXPORTER` | `otlp` | Con `otlp` exporta métricas; cualquier otro valor deja el lector de métricas vacío. |
| `OTEL_LOGS_EXPORTER` | `otlp` | Con `otlp` el SDK adjunta un `LoggingHandler` al logger `app` y exporta los logs de `app.*` por OTLP, incluido el traceback redactado; los terceros y Uvicorn no se exportan. Sin `otlp` no se adjunta el handler. Los logs de `app.*` siguen saliendo por `stdout`. |
| `SIMULAR_LATENCIA_MS` | `0` | Latencia artificial para el simulacro EC-11. **Solo para entornos de prueba**; en producción debe ser `0`. El guard solo reconoce exactamente `ENTORNO=production`. |

> [!IMPORTANT]
> No incluyas credenciales reales en `.env.example` ni en este documento. Usa únicamente placeholders y mantén `OTEL_EXPORTER_OTLP_HEADERS` fuera del control de versiones.

La política de trazas es **errores primero**: se exportan el 100 % de los errores y el `OTEL_TRACES_SAMPLER_ARG` de los éxitos (20 % por defecto); las métricas no se muestrean. El procedimiento operativo, el SLO, la alerta y la reversión están en el [runbook de observabilidad](observabilidad.md).

### 3. Inicialización de Backend, Base de Datos y Semilla

```powershell
# Sincronizar dependencias del backend
uv --directory backend sync --dev

# Verificar conectividad PostgreSQL (Pooler), Redis y Supabase Storage
uv --directory backend run python ../scripts/verificar_conexion.py

# Aplicar migraciones idempotentes (0001, 0002, 0003, 0005, 0006 y 0007)
uv --directory backend run python ../scripts/migrar.py

# Cargar catálogo inicial de productos, presentaciones, tiendas y precios semilla
uv --directory backend run python ../scripts/semilla.py

# Opcional: sembrar 90 días de historial demo para la gráfica A2 / EC-08
uv --directory backend run python ../scripts/semilla_historial.py
```

El script de historial es **opcional** y se ejecuta después de `semilla.py` (requiere el perfil
semilla `vecino_centenario`). Genera puntos históricos deterministas marcados con
`es_demo = true`, es idempotente (`ON CONFLICT (id) DO NOTHING`) y **no modifica
`precio_vigente`**, por lo que no altera la comparación vigente.

### 4. Levantar Backend y Frontend en Desarrollo

```powershell
# Terminal 1: API FastAPI en http://127.0.0.1:8000 (Swagger en /docs)
uv --directory backend run uvicorn app.main:app --reload --port 8000

# Terminal 2: Generar cliente OpenAPI tipado (opcional tras cambios de esquema) e iniciar Next.js
npm --prefix frontend install
npm --prefix frontend run api:generar
npm --prefix frontend run dev
```

La aplicación queda disponible en `http://127.0.0.1:3000` (o en ambos servicios mediante [scripts/dev.cmd](../scripts/dev.cmd)).

---

## Parte II — Despliegue en Producción de Costo Cero

| Componente | Proveedor recomendado | Artefacto / Origen | Notas clave |
|---|---|---|---|
| **Base de Datos + Auth + Storage** | **Supabase Free** | [supabase/migrations/](../supabase/migrations/0001_fundaciones_seguridad.sql) | Bucket privado `fotos-precios`; rol `app_backend` sin `DELETE` en evidencia |
| **Caché L2 + Rate Limiting** | **Upstash Redis Free** | Conexión TLS `rediss://` | 10 000 req/día en capa gratuita; caché `TTL = 60 s` |
| **Backend API** | **Railway** o **Render Free** | [backend/Dockerfile](../backend/Dockerfile) | Usar **Transaction Pooler (puerto `6543`)** de Supabase en producción |
| **Frontend PWA** | **Vercel Hobby** | Carpeta `frontend/` | Root Directory = `frontend`, Framework Preset = `Next.js` |
| **Jobs Programados** | **GitHub Actions** | [jobs.yml](../.github/workflows/jobs.yml) | Ejecución horaria/diaria contra `/internal/jobs/{nombre}` |
| **Observabilidad B1** | **Grafana Cloud** o colector OTLP | [infra/observabilidad/](../infra/observabilidad/README.md) | Métricas, trazas y logs de `app.*` por OTLP/HTTP; tablero y reglas versionados; cuota y retención por confirmar (`PA-05`) |

### Paso 1 — Supabase y Upstash
1. Ejecuta `scripts/migrar.py` y `scripts/semilla.py` apuntando al proyecto productivo de Supabase.
2. Verifica en **Storage** de Supabase la existencia del bucket `fotos-precios`.
3. En **Database -> Connection Pooling**, copia la cadena del **Transaction Pooler (puerto `6543`)** para el backend en la nube (`DATABASE_URL`), manteniendo `ssl=require` compatible con `asyncpg`.

### Paso 2 — Backend Contenerizado (`backend/Dockerfile`) en Render o Railway
El archivo [backend/Dockerfile](../backend/Dockerfile) utiliza construcción multi-etapa (`python:3.12-slim`), usuario no privilegiado `appuser` y `HEALTHCHECK` automático sobre `/v1/salud`.
1. Crea un nuevo servicio web apuntando al repositorio GitHub con **Root Directory = `backend`** y **Dockerfile Path = `backend/Dockerfile`**.
2. Configura las variables de entorno en el panel del proveedor:
   - `ENTORNO=production`
   - `SIMULAR_LATENCIA_MS=0`
   - `DATABASE_URL` (Transaction Pooler puerto `6543` con credenciales de `app_backend`)
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
   - `REDIS_URL` (endpoint TLS `rediss://...` de Upstash)
   - `HUELLA_SECRETO_MAESTRO`, `JOB_TOKEN`
   - `CORS_ORIGINS=["https://<tu-frontend>.vercel.app"]`
   - Las variables OTel del [apartado anterior](#variables-de-observabilidad-opentelemetry-b1), con endpoint y cabeceras guardados como secretos.
3. Verifica el despliegue consultando `https://<tu-backend>.onrender.com/v1/salud` (debe responder HTTP `200`).

### Paso 3 — Frontend PWA en Vercel
1. Importa el repositorio en Vercel estableciendo **Root Directory = `frontend`**.
2. Define las variables de entorno en Vercel:
   - `NEXT_PUBLIC_API_URL=https://<tu-backend>.onrender.com`
   - `NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>`
3. Despliega y verifica que el manifiesto PWA (`/manifest.webmanifest`) y las rutas (`/`, `/producto/[id]`, `/reportar`, `/ingresar`, `/gestion`, `/legal`) carguen con HTTPS.

### Paso 4 — Secretos y Jobs Programados en GitHub Actions
El workflow [.github/workflows/jobs.yml](../.github/workflows/jobs.yml) invoca automáticamente los endpoints internos protegidos por cabecera `X-Job-Token`:
- Cada **15 minutos**: `POST /internal/jobs/limpiar-idempotencia`
- Cada **hora**: `POST /internal/jobs/recalcular-vencimientos`
- **Diario (05:00 UTC)**: `POST /internal/jobs/purgar-huellas` y `POST /internal/jobs/cerrar-disputas-vencidas`

Para activarlo en GitHub:
1. Ve a **Settings -> Secrets and variables -> Actions** del repositorio.
2. Crea exactamente dos secretos de repositorio (**Repository secrets**):
   - **`BACKEND_URL`**: URL pública del backend sin barra final (ej. `https://comparador-api.onrender.com`).
   - **`JOB_TOKEN`**: mismo secreto alfanumérico largo configurado en la variable `JOB_TOKEN` del backend en Render/Railway.
3. Ejecuta manualmente el workflow desde la pestaña **Actions -> Jobs internos programados -> Run workflow** (`limpiar-idempotencia`) y confirma estado verde (`HTTP 200`).

### Paso 5 — Observabilidad en producción (B1)

1. Crea un stack en **Grafana Cloud** (o un colector OTLP compatible) y genera una credencial de escritura para métricas, trazas y logs. La credencial es un secreto: no la escribas en este documento, en `.env.example` ni en el repositorio.
2. En el panel del backend (Render/Railway) configura, además de las variables del Paso 2:
   - `OTEL_SDK_DISABLED=false`
   - `OTEL_SERVICE_NAME=comparador-precios-backend`
   - `OTEL_EXPORTER_OTLP_ENDPOINT=<url-base-otlp-del-proveedor>`
   - `OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <credencial-base64>` como **secreto del proveedor**
   - `OTEL_TRACES_SAMPLER=parentbased_traceidratio` (declarativa; no altera el muestreo actual)
   - `OTEL_TRACES_SAMPLER_ARG=0.2`
   - `OTEL_METRICS_EXPORTER=otlp`
   - `OTEL_LOGS_EXPORTER=otlp`
   - `SIMULAR_LATENCIA_MS=0`

   `OTEL_TRACES_SAMPLER` es declarativa: la inicialización crea los spans con `ALWAYS_ON` y el procesador errores-primero decide la exportación. La proporción efectiva de éxitos la fija `OTEL_TRACES_SAMPLER_ARG`.

3. Importa o aprovisiona el tablero siguiendo [`infra/observabilidad/README.md`](../infra/observabilidad/README.md#cómo-cargar-el-tablero) y elige como datasource la fuente Prometheus/Mimir que recibe las métricas del colector.
4. Carga las reglas de [`slo-comparador.yml`](../infra/observabilidad/grafana/alertas/slo-comparador.yml) con `mimirtool` o `promtool`, según el motor. Configura el contact point y la política de notificación en Grafana Cloud; esa configuración vive fuera del repositorio.
5. Reinicia el backend y verifica:
   - `GET https://<tu-backend>/v1/salud` responde HTTP `200`.
   - Tras una petición, `stdout` contiene una línea `INFO app.acceso` con `trace_id`, `span_id` y la URL redactada.
   - Al generar tráfico de comparación aparecen datos en el tablero.
   - Los INFO de terceros no aparecen; sus WARNING/ERROR salen por `stderr` redactados. Los logs de Uvicorn no se exportan por OTLP.

> [!IMPORTANT]
> La configuración anterior deja el mecanismo listo, pero **no certifica** que los nombres de métricas, la retención ni el disparo de la alerta estén validados contra el proveedor real. Esa verificación es **T-126** y debe guardar evidencia. El procedimiento completo de operación, diagnóstico y reversión está en [`docs/observabilidad.md`](observabilidad.md).

