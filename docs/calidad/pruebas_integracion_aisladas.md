# Pruebas de integración en base aislada

Las pruebas de `backend/tests/integracion/` necesitan PostgreSQL, PostGIS y las
migraciones aplicadas. Para no escribir en la base de la aplicación ni depender de
Docker, se usa una base separada en el mismo proyecto de Supabase:
`comparador_pruebas`.

## Requisitos

- `backend/.venv` con las dependencias del proyecto.
- `.env` en la raíz con `DATABASE_URL` y `MIGRATIONS_DATABASE_URL`.
- El rol de migraciones debe poder crear bases (`CREATEDB`) y aplicar extensiones.

## Uso

```bash
# Recrear la base, aplicar migraciones, sembrar datos y correr toda la suite
backend/.venv/bin/python scripts/integracion_aislada.py --recrear --con-semilla

# Ejecutar solo un archivo o una prueba
backend/.venv/bin/python scripts/integracion_aislada.py --con-semilla -- \
  -q tests/integracion/test_historial_precios.py

# Conservar la base para depurar un fallo
backend/.venv/bin/python scripts/integracion_aislada.py --recrear --con-semilla --mantener

# Eliminar la base de pruebas
backend/.venv/bin/python scripts/integracion_aislada.py --eliminar
```

El script:

1. se niega a operar sobre cualquier base distinta de `comparador_pruebas`;
2. crea la base si no existe y aplica `supabase/migrations/` en orden;
3. opcionalmente ejecuta `scripts/semilla.py`;
4. ejecuta `pytest tests/integracion` con `DATABASE_URL` en modo `asyncpg`;
5. elimina la base al terminar, salvo `--mantener` o si la suite falla.

No imprime contraseñas ni escribe credenciales en archivos. No usa Docker.

## T-68

La evidencia de T-68 se obtiene con una base recreada desde cero:

```bash
backend/.venv/bin/python scripts/integracion_aislada.py --recrear --con-semilla
```

El resultado debe registrar el total de pruebas, los fallos y el tiempo. No se
ejecuta contra la base compartida de la aplicación.
