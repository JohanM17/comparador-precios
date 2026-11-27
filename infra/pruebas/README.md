# Base de datos desechable para pruebas de integración

## Por qué existe

La suite de `backend/tests/integracion` escribe de verdad: crea reportes, cuentas, casos de
moderación y precios. No envuelve sus escrituras en una transacción que revierta, así que
**correrla contra la base compartida del equipo dejaría datos de prueba mezclados con los
reales**, y además pisaría las mediciones de rendimiento que estén en curso.

Esta base vive en un contenedor, se crea en segundos y se destruye con todo lo que escribió
dentro. Cada corrida parte de cero, que es justo lo que una prueba de integración necesita para
ser repetible.

## Qué tiene de particular

Postgres a secas no trae los roles `anon` y `authenticated`, que sí trae Supabase. La migración
`0001` les revoca privilegios sobre el esquema público (`ADR-012`), y sin esos roles la sentencia
falla y **ninguna** migración aplica. Por eso `00_roles.sql` los crea antes que nada; el
contenedor lo ejecuta solo, al inicializarse.

La imagen es `postgis/postgis`, que ya incluye PostGIS. Las demás extensiones que pide `0001`
(`pg_trgm`, `unaccent`, `pgcrypto`) vienen en cualquier Postgres.

El puerto es **55432** y no 5432, para no chocar con un Postgres que ya esté instalado en la
máquina.

## Cómo se usa

```bash
docker compose -f infra/pruebas/docker-compose.yml up -d
```

Con el contenedor arriba, apuntar las dos variables de conexión a él y preparar el esquema:

```bash
export DATABASE_URL="postgresql+asyncpg://postgres:pruebas_locales@127.0.0.1:55432/postgres"
export MIGRATIONS_DATABASE_URL="$DATABASE_URL"
python scripts/migrar.py
python scripts/semilla.py
pytest backend/tests/integracion
```

En PowerShell:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:pruebas_locales@127.0.0.1:55432/postgres"
```

```powershell
$env:MIGRATIONS_DATABASE_URL = $env:DATABASE_URL
```

```powershell
python scripts/migrar.py; if ($?) { python scripts/semilla.py }
```

```powershell
pytest backend/tests/integracion
```

Al terminar, el `-v` es lo que importa: borra el volumen y con él todo lo que las pruebas
escribieron.

```bash
docker compose -f infra/pruebas/docker-compose.yml down -v
```

## Lo que esta base no reemplaza

No es un staging ni un ensayo de producción. No tiene RLS aplicada con los roles reales de
Supabase, no tiene el *pooler* en medio y sus tiempos de respuesta no se parecen a los de la nube
(las mediciones de `EC-04` y `EC-08` se hacen contra el backend desplegado, no aquí). Sirve para
una sola cosa: ejecutar las pruebas de integración sin tocar datos de nadie.
