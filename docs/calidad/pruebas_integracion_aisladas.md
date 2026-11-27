# Pruebas de integración en base aislada

Las pruebas de `backend/tests/integracion/` necesitan PostgreSQL, PostGIS y las
migraciones aplicadas. Para no escribir en la base de la aplicación ni depender de
Docker, se usa una base separada en el mismo proyecto de Supabase:
`comparador_pruebas`.

## Requisitos

- `backend/.venv` con las dependencias del proyecto.
- `.env` en la raíz con `DATABASE_URL`, `MIGRATIONS_DATABASE_URL` y
  `SUPABASE_URL`.
- El rol de migraciones debe poder crear bases (`CREATEDB`) y aplicar extensiones.
- La URL de BD debe usar el usuario `postgres.<project_ref>` del mismo proyecto
  que `SUPABASE_URL`; el script aborta si no coinciden.

## Uso

```bash
# Recrear la base, aplicar migraciones, sembrar datos y correr toda la suite
backend/.venv/bin/python scripts/integracion_aislada.py --recrear --con-semilla

# Ejecutar solo un archivo (no toda la suite)
backend/.venv/bin/python scripts/integracion_aislada.py --mantener -- \
  -q tests/integracion/test_disputa_durabilidad.py

# Ejecutar un node id concreto
backend/.venv/bin/python scripts/integracion_aislada.py --mantener -- \
  tests/integracion/test_disputa_durabilidad.py::test_confirmar_es_durable_y_solo_reportes_posteriores_reabren

# Conservar la base para depurar un fallo
backend/.venv/bin/python scripts/integracion_aislada.py --recrear --con-semilla --mantener

# Eliminar la base de pruebas
backend/.venv/bin/python scripts/integracion_aislada.py --eliminar
```

El script:

1. valida que la BD y `SUPABASE_URL` apunten al mismo cluster y muestra el host
   ofuscado que usará, sin credenciales;
2. se niega a operar sobre cualquier base distinta de `comparador_pruebas`;
3. crea la base si no existe y aplica `supabase/migrations/` en orden;
4. opcionalmente ejecuta `scripts/semilla.py`;
5. ejecuta `pytest` sobre `tests/integracion` o sobre el archivo/node id
   indicado, con `DATABASE_URL` en modo `asyncpg`;
6. elimina la base al terminar, salvo `--mantener` o si la suite falla.

No imprime contraseñas ni escribe credenciales en archivos. No usa Docker.

## Serialización y `--force`

Las corridas sobre `comparador_pruebas` deben serializarse: dos suites
concurrentes comparten filas y locks y pueden hacer fallar pruebas de jobs.

- `--recrear` y `--eliminar` consultan `pg_stat_activity` antes de terminar
  conexiones o dropear la base. Si hay conexiones ajenas, abortan con un mensaje
  claro.
- `--force` permite cerrar esas conexiones y continuar; úsalo solo cuando sepas
  que no hay otra corrida legítima en curso.
- Las operaciones destructivas toman un advisory lock de PostgreSQL para que dos
  scripts no se pisen al recrear o eliminar la base.

## T-68

La evidencia de T-68 se obtiene con una base recreada desde cero:

```bash
backend/.venv/bin/python scripts/integracion_aislada.py --recrear --con-semilla
```

El resultado debe registrar el total de pruebas, los fallos y el tiempo. No se
ejecuta contra la base compartida de la aplicación.
