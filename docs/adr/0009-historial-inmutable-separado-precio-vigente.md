# ADR-009: Historial Inmutable reporte_precio Separado de precio_vigente

## Estado
Aceptado

## Contexto
Calcular el precio de comparación ejecutando agregaciones pesadas (`AVG`, `MEDIAN`, filtros de fecha y descartes de reportes anómalos) sobre toda la tabla histórica de reportes en cada petición pública resulta inviable para mantener latencias < 200 ms bajo concurrencia (`EC-04`). Por otro lado, sobrescribir directamente el precio de una tienda destruye la evidencia forense necesaria para auditar anomalías, sanciones y evolución de la canasta familiar.

## Alternativas consideradas
1. **Modelo relacional tradicional de tabla única (`precio_producto` con UPDATE):** Se sobrescribe el precio con cada reporte. Destruye la trazabilidad histórica, impide auditorías y anula la detección de ráfagas retrospectivas (`EC-03`).
2. **Cálculo al vuelo con consultas agregadas complejas:** Requiere escanear decenas de miles de filas en cada búsqueda, colapsando la base de datos bajo ráfagas de usuarios.
3. **CQRS ligero en la misma base de datos (Escritura inmutable vs. Lectura precalculada):**
   - *Escritura (Comando):* Inserción append-only en `reporte_precio` con triggers que prohíben modificaciones y borrados.
   - *Lectura (Consulta):* Tabla desnormalizada `precio_vigente` actualizada en la misma transacción mediante funciones de dominio deterministas.

## Decisión
Separar estructuralmente el modelo de datos en:
1. `reporte_precio`: Registro histórico estrictamente inmutable (*append-only*) de cada observación enviada por usuarios o comercios.
2. `precio_vigente`: Tabla de lectura precalculada indexada por `(presentacion_id, establecimiento_id)` que mantiene el precio representativo actual, sello asignado y fecha de cálculo.

Al aceptarse un reporte, la fila de `precio_vigente` se recalcula sincrónicamente dentro de la misma transacción de base de datos.

## Consecuencias
### Positivas
- Consultas públicas de comparación leen una sola fila indexada por presentación y tienda en $< 5$ ms.
- Inmutabilidad y trazabilidad legal absoluta de las evidencias de precios recolectadas.
- Sincronización inmediata entre reportes y precios visibles sin inconsistencias de lectura.

### Negativas
- Sobrecosto menor de almacenamiento por duplicidad entre historial y tabla vigente.
