# ADR-005: Persistencia en Supabase (PostgreSQL + PostGIS, Auth, Storage) frente a NoSQL

## Estado
Aceptado

## Contexto
El sistema necesita almacenar relaciones estructuradas complejas (productos, presentaciones, categorías, establecimientos, reportes de precios, precios vigentes, auditoría), realizar búsquedas geográficas por proximidad en metros con radio ajustable, autenticar usuarios de manera segura y alojar evidencias fotográficas comprimidas sin metadatos.

## Alternativas consideradas
1. **Bases de datos NoSQL (MongoDB / DynamoDB / Firebase Firestore):** Flexibles en esquema pero deficientes para transacciones ACID multi-tabla requeridas al actualizar `precio_vigente` concurrentemente. Las consultas geoespaciales complejas y la normalización de productos resultan frágiles sin integridad referencial estricta.
2. **PostgreSQL auto-hospedado en VPS:** Requiere administración de infraestructura, backups manuales y configuración separada de almacenamiento S3 y servidor de autenticación, inviable para presupuesto cero y equipo de 4.
3. **Supabase (PostgreSQL administrado + PostGIS + GoTrue Auth + S3 Storage):** Plataforma integral gratuita con motor relacional PostgreSQL 15+, extensión geoespacial nativa `postgis`, extensiones de texto `pg_trgm` y `unaccent`, autenticación JWT estándar y almacenamiento de objetos S3.

## Decisión
Adoptar **Supabase** como plataforma de persistencia principal, utilizando su base de datos PostgreSQL con extensiones `postgis`, `pg_trgm`, `unaccent` y `pgcrypto`. Se utiliza Supabase Auth para emisión de JWTs y Supabase Storage para alojar imágenes de prueba depuradas de metadatos EXIF.

## Consecuencias
### Positivas
- Integridad referencial estricta y transaccionalidad ACID para evitar precios corruptos.
- Búsqueda espacial de alta precisión (`ST_DWithin`, `ST_Distance`) indexada con `GIST`.
- Búsqueda difusa de productos tolerante a tildes y errores tipográficos.
- Costo cero dentro del nivel gratuito oficial de Supabase.

### Negativas
- Límite de 500 MB en base de datos en la capa gratuita (mitigado por esquema normalizado y purga de huellas temporales a los 30 días).
- Pausa automática por inactividad a los 7 días (mitigado con job de ping programado en GitHub Actions).
