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
DATABASE_URL_ADMIN=postgresql://postgres.<project-ref>:<PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
SUPABASE_JWT_SECRET=<jwt-secret>
REDIS_URL=rediss://default:<UPSTASH_TOKEN>@<endpoint>.upstash.io:6379
HUELLA_RED_PEPPER=<cadena-aleatoria-32-chars>
JOB_TOKEN=<token-jobs-internos-32-chars>
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
```

> [!IMPORTANT]
> En redes locales Windows sin enrutamiento IPv6 hacia Supabase, utiliza siempre la URL del **Session Pooler (puerto `5432`, host `*.pooler.supabase.com`)** para migraciones y desarrollo local. No subas el archivo `.env` al repositorio.

#### Variables de observabilidad (OpenTelemetry, B1)

Estas variables configuran la telemetría de la ampliación B1 (trazas, métricas y logs vía OTLP/HTTP). El SDK se inicializa en las tareas `T-103` y `T-120`; por ahora solo se declaran y documentan.

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `OTEL_SDK_DISABLED` | `false` | Con `true` desactiva toda la telemetría y deja la API operativa. Es el interruptor de emergencia. |
| `OTEL_SERVICE_NAME` | `comparador-precios-backend` | Nombre del servicio que aparece en trazas y métricas. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | vacío | Endpoint OTLP/HTTP del colector (Grafana Cloud o equivalente). Obligatorio cuando B1 está activo. |
| `OTEL_EXPORTER_OTLP_HEADERS` | vacío | Cabeceras de autenticación del colector, por ejemplo `Authorization=Basic <credencial>`. **Es un secreto**: configúralo en el panel del proveedor o en GitHub Secrets, nunca en el repositorio. |
| `OTEL_TRACES_SAMPLER` | `parentbased_traceidratio` | Estrategia de muestreo de trazas. |
| `OTEL_TRACES_SAMPLER_ARG` | `0.2` | Proporción de trazas exitosas muestreadas; los errores se muestrean al 100 %. |
| `OTEL_METRICS_EXPORTER` | `otlp` | Exportador de métricas. |
| `OTEL_LOGS_EXPORTER` | `otlp` | Exportador de logs cuando se habilite. |
| `SIMULAR_LATENCIA_MS` | `0` | Latencia artificial para el simulacro EC-11. **Solo para entornos de prueba**; en producción debe ser `0`. |

> [!IMPORTANT]
> No incluyas credenciales reales en `.env.example` ni en este documento. Usa únicamente placeholders y mantén `OTEL_EXPORTER_OTLP_HEADERS` fuera del control de versiones.

### 3. Inicialización de Backend, Base de Datos y Semilla

```powershell
# Sincronizar dependencias del backend
uv --directory backend sync --dev

# Verificar conectividad PostgreSQL (Pooler), Redis y Supabase Storage
uv --directory backend run python ../scripts/verificar_conexion.py

# Aplicar migraciones idempotentes (0001, 0002, 0003)
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

La aplicación queda disponible en `http://127.0.0.1:3000` (o en ambos servicios mediante [scripts/dev.cmd](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/scripts/dev.cmd)).

---

## Parte II — Despliegue en Producción de Costo Cero

| Componente | Proveedor recomendado | Artefacto / Origen | Notas clave |
|---|---|---|---|
| **Base de Datos + Auth + Storage** | **Supabase Free** | [supabase/migrations/](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/supabase/migrations/0001_fundaciones_seguridad.sql) | Bucket privado `fotos-precios`; rol `app_backend` sin `DELETE` en evidencia |
| **Caché L2 + Rate Limiting** | **Upstash Redis Free** | Conexión TLS `rediss://` | 10 000 req/día en capa gratuita; caché `TTL = 60 s` |
| **Backend API** | **Railway** o **Render Free** | [backend/Dockerfile](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/backend/Dockerfile) | Usar **Transaction Pooler (puerto `6543`)** de Supabase en producción |
| **Frontend PWA** | **Vercel Hobby** | Carpeta `frontend/` | Root Directory = `frontend`, Framework Preset = `Next.js` |
| **Jobs Programados** | **GitHub Actions** | [jobs.yml](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/.github/workflows/jobs.yml) | Ejecución horaria/diaria contra `/internal/jobs/{nombre}` |

### Paso 1 — Supabase y Upstash
1. Ejecuta `scripts/migrar.py` y `scripts/semilla.py` apuntando al proyecto productivo de Supabase.
2. Verifica en **Storage** de Supabase la existencia del bucket `fotos-precios`.
3. En **Database -> Connection Pooling**, copia la cadena del **Transaction Pooler (puerto `6543`)** para el backend en la nube (`DATABASE_URL`), manteniendo `ssl=require` compatible con `asyncpg`.

### Paso 2 — Backend Contenerizado (`backend/Dockerfile`) en Render o Railway
El archivo [backend/Dockerfile](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/backend/Dockerfile) utiliza construcción multi-etapa (`python:3.12-slim`), usuario no privilegiado `appuser` y `HEALTHCHECK` automático sobre `/v1/salud`.
1. Crea un nuevo servicio web apuntando al repositorio GitHub con **Root Directory = `backend`** y **Dockerfile Path = `backend/Dockerfile`**.
2. Configura las variables de entorno en el panel del proveedor:
   - `ENVIRONMENT=production`
   - `DATABASE_URL` (Transaction Pooler puerto `6543` con credenciales de `app_backend`)
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
   - `REDIS_URL` (endpoint TLS `rediss://...` de Upstash)
   - `HUELLA_RED_PEPPER`, `JOB_TOKEN`
   - `CORS_ORIGINS=["https://<tu-frontend>.vercel.app"]`
3. Verifica el despliegue consultando `https://<tu-backend>.onrender.com/v1/salud` (debe responder HTTP `200`).

### Paso 3 — Frontend PWA en Vercel
1. Importa el repositorio en Vercel estableciendo **Root Directory = `frontend`**.
2. Define las variables de entorno en Vercel:
   - `NEXT_PUBLIC_API_URL=https://<tu-backend>.onrender.com`
   - `NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>`
3. Despliega y verifica que el manifiesto PWA (`/manifest.webmanifest`) y las rutas (`/`, `/producto/[id]`, `/reportar`, `/ingresar`, `/gestion`, `/legal`) carguen con HTTPS.

### Paso 4 — Secretos y Jobs Programados en GitHub Actions
El workflow [.github/workflows/jobs.yml](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/.github/workflows/jobs.yml) invoca automáticamente los endpoints internos protegidos por cabecera `X-Job-Token`:
- Cada **15 minutos**: `POST /internal/jobs/limpiar-idempotencia`
- Cada **hora**: `POST /internal/jobs/recalcular-vencimientos`
- **Diario (05:00 UTC)**: `POST /internal/jobs/purgar-huellas` y `POST /internal/jobs/cerrar-disputas-vencidas`

Para activarlo en GitHub:
1. Ve a **Settings -> Secrets and variables -> Actions** del repositorio.
2. Crea exactamente dos secretos de repositorio (**Repository secrets**):
   - **`BACKEND_URL`**: URL pública del backend sin barra final (ej. `https://comparador-api.onrender.com`).
   - **`JOB_TOKEN`**: mismo secreto alfanumérico largo configurado en la variable `JOB_TOKEN` del backend en Render/Railway.
3. Ejecuta manualmente el workflow desde la pestaña **Actions -> Jobs internos programados -> Run workflow** (`limpiar-idempotencia`) y confirma estado verde (`HTTP 200`).

