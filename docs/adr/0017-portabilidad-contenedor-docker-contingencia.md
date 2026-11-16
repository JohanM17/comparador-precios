# ADR-017: Portabilidad del Contenedor Docker hacia Render Free y Fly.io

## Estado
Aceptado

## Contexto
El despliegue del backend FastAPI en Railway aprovecha el crédito inicial de prueba de $5 USD. Al agotarse este saldo o si la política de la plataforma cambia, el sistema no puede quedar fuera de línea durante el desarrollo académico ni durante la evaluación del Corte 2 y Corte 3. Es imperativo que la aplicación pueda migrarse de proveedor en cuestión de minutos sin alterar una sola línea de código fuente.

## Alternativas consideradas
1. **Acoplarse a APIs o servicios específicos de un proveedor (ej. Railway Nixpacks exclusivos o AWS App Runner):** Genera dependencia de proveedor (*vendor lock-in*) y dificulta la migración de emergencia.
2. **Reescribir el backend como funciones Serverless (AWS Lambda o Vercel Serverless Functions):** Requiere reconfigurar adaptadores de conexión a base de datos, lidiar con arranques en frío extremos y reescribir la gestión de tareas de fondo.
3. **Contenedor OCI estándar (Dockerfile multi-etapa agnóstico de la plataforma):**
   - Construcción con `hatchling` y Python 3.12 en etapas separadas (`builder` y `runtime`).
   - Usuario sin privilegios `appuser` (UID 10001).
   - Configuración exclusivamente mediante variables de entorno estándar (`PORT`, `DATABASE_URL`, `REDIS_URL`).
   - `HEALTHCHECK` estandarizado contra `/v1/salud`.

## Decisión
Estandarizar el empaquetado del backend de FastAPI en un **`Dockerfile` multi-etapa agnóstico** y portable. Si se agota el crédito de Railway, el contenedor puede desplegarse de inmediato en las capas gratuitas de **Render Free** o **Fly.io** vinculando el repositorio de GitHub y aprovisionando las mismas variables de entorno sin modificar la base de código.

## Consecuencias
### Positivas
- Cero dependencia de proveedor y garantía de disponibilidad continua a costo cero.
- Seguridad de contenedores: ejecución con usuario sin privilegios y superficie de ataque reducida.
- Proceso de despliegue reproducible verificado en integración continua.

### Negativas
- En planes gratuitos como Render Free, la instancia se suspende tras 15 minutos de inactividad (el job `ping_bd` ayuda a mitigar esto).
