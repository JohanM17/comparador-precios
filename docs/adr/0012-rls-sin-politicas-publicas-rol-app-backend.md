# ADR-012: RLS sin Políticas Públicas y Conexión Exclusiva con Rol app_backend

## Estado
Aceptado

## Contexto
En arquitecturas basadas en Supabase es común depender de Row Level Security (RLS) para filtrar datos directamente a clientes web. Sin embargo, en este proyecto toda la lógica de negocio, control de acceso, neutralidad comercial, anonimización por Ley 1581 y auditoría se gestiona centralizadamente en FastAPI. Si se dejan políticas permisivas en RLS para los roles `anon` o `authenticated`, cualquier atacante con la clave anónima pública de Supabase podría consultar directamente la base de datos evadiendo las reglas de la API.

## Alternativas consideradas
1. **Acceso directo vía PostgREST con políticas RLS públicas complejas:** Muy propenso a fugas de seguridad, difícil de auditar y propenso a exponer coordenadas GPS, huellas de red o algoritmos de detección.
2. **Conexión del backend con el superusuario `postgres`:** Violación del principio de mínimo privilegio; un fallo de inyección SQL permitiría alterar la configuración del motor de base de datos o el esquema.
3. **RLS habilitada por defecto sin políticas para `anon`/`authenticated` y rol dedicado `app_backend`:**
   - Revocar `ALL PRIVILEGES` a `anon` y `authenticated` sobre el esquema `public`.
   - Crear rol con mínimo privilegio `app_backend` con permisos específicos DML (`SELECT`, `INSERT`, `UPDATE` restringido) sobre tablas públicas.
   - Otorgar `BYPASSRLS` a `app_backend` para permitir operaciones de backend transparentes manteniendo el aislamiento total de los roles externos.

## Decisión
Habilitar **Row Level Security (RLS) en todas las tablas del esquema `public` sin conceder políticas públicas** a los roles de Supabase `anon` y `authenticated`. El backend de FastAPI opera de manera exclusiva asumiendo el rol con privilegio mínimo **`app_backend`** en cada transacción (`SET LOCAL ROLE app_backend;`).

## Consecuencias
### Positivas
- Blindaje absoluto contra accesos no autorizados a través de los endpoints REST/GraphQL de Supabase.
- Aislamiento verificado por pruebas automáticas (`test_seguridad_bd.py`).
- Principio de mínimo privilegio respetado en el acceso del backend a las tablas del sistema.

### Negativas
- Requiere ejecutar migraciones DDL con un rol con privilegios elevados (`postgres`), mientras que el runtime de la aplicación usa `app_backend`.
