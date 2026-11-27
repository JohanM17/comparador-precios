# ADR-0019: Historial de Precios de 90 Días sobre el Registro Append-Only y Conservación del Precio Oficial (EC-08)

## Estado

Aceptado — 2026-11-25.

Implementado en `T-110` a `T-119`. `EC-08` se verificó con 13/13 pruebas de integración, E2E 19/19 y axe sin violaciones críticas. La escritura del historial oficial (`fuente='comercio'`) queda coordinada con `T-63` del módulo comercial; la medición p95 con 100 puntos queda pendiente de registrar.

## Contexto

La ampliación A2 exige que el consumidor consulte la serie de los últimos 90 días de un producto en un establecimiento, con el origen de cada dato (oficial, reportado o fuente pública) y su estado de confiabilidad, sin sobrescribir los valores anteriores (`EC-08`). El núcleo ya dispone de `reporte_precio` como evidencia histórica append-only y de `precio_vigente` como proyección materializada para la comparación. El módulo comercial (Etapa 2) introduce `precio_oficial`, que por diseño se actualiza con `UPSERT` y, si no se modifica, perdería las versiones anteriores. Además, el historial no puede identificar al reportante (Ley 1581).

Fuerzas:

- Reutilizar el historial inmutable existente y no duplicar la fuente de verdad.
- Incluir el precio oficial sin romper la neutralidad ni el orden de comparación.
- Mantener la consulta simple y dentro del presupuesto de costo cero.
- No introducir Event Sourcing si el registro append-only ya satisface el escenario.
- Preservar la privacidad y no exponer `reportante_id`, alias, foto ni coordenadas.

## Alternativas consideradas

1. **Event Sourcing completo (event store + proyecciones):** permitiría reconstruir cualquier estado, pero añade infraestructura, versionado de eventos, proyecciones y operación que el proyecto no necesita para una serie de 90 días. Además, duplicaría el historial que `reporte_precio` ya conserva.
2. **Tabla `historial_precio` separada con snapshots:** aislaría la serie, pero crea una segunda fuente de verdad que debe sincronizarse con `reporte_precio` y `precio_vigente`; aumenta el riesgo de inconsistencias y el costo de mantenimiento.
3. **Usar `reporte_precio` como fuente única y agregar el precio oficial como un reporte con `fuente = 'comercio'`:** reutiliza la tabla append-only, conserva todas las versiones y permite que la serie incluya precios oficiales y reportados con el mismo contrato. Es la alternativa elegida.

## Decisión

Se adopta la alternativa 3:

- La serie se consulta desde `reporte_precio` por `producto_id`, `establecimiento_id`, `presentacion_id` opcional y rango de 90 días.
- Cada cambio de precio oficial del módulo comercial se registra como una nueva fila en `reporte_precio` con `fuente = 'comercio'`, `estado = 'aceptado'` y `estado_original = 'aceptado'`, sin sobrescribir la fila anterior. La escritura se coordina con `T-63`.
- La serie incluye reportes `aceptado` y `dudoso`; los `rechazado` no se presentan como precio histórico válido. Los `dudoso` se muestran con una marca explícita y nunca como `confiable`.
- El origen se expone como `usuario`, `comercio` o `semilla`; `semilla` se etiqueta como fuente pública/demostración y conserva `es_demo`.
- La respuesta no incluye `reportante_id`, alias, correo, IP, `huella_red`, `foto_prueba_path`, `lat` ni `lng`.
- Se añade un índice aditivo para la consulta por producto/establecimiento/fecha, en `0005_historial_precios.sql`. Se aplicó antes que la migración del módulo comercial, que por eso quedó como `0006_modulo_comercial.sql`.
- No se introduce Event Sourcing ni una tabla de historial separada.

## Consecuencias

### Positivas

- Una sola fuente de verdad append-only, ya auditada y protegida por triggers.
- El historial oficial y el reportado comparten el mismo contrato y la misma consulta.
- No se duplica información ni se añade un almacén nuevo.
- La serie puede auditarse y reconstruirse; los cambios no se pierden.
- Bajo costo operativo y de almacenamiento para el volumen esperado.

### Negativas

- El módulo comercial debe escribir el precio oficial en `reporte_precio`, además de su tabla `precio_oficial`; es una responsabilidad adicional que debe probarse.
- La proyección `precio_vigente` debe seguir recalculándose correctamente cuando llega una fila `fuente='comercio'`.
- La consulta de 90 días requiere un índice adecuado y un límite de puntos para evitar respuestas grandes.
- Los reportes `dudoso` pueden generar ruido visual; se mitiga con marcas y filtros.

### Riesgos aceptados

- Duplicación controlada entre `precio_oficial` y la fila histórica de `reporte_precio`; la fuente de verdad histórica es `reporte_precio`.
- Si el módulo comercial no implementa la escritura histórica, A2 queda incompleto; se registra como dependencia bloqueante.

## Verificación

- Prueba de integración con reportes en días 1, 30, 60 y 90: orden, origen y estado.
- Prueba de cambio oficial: se inserta una fila `fuente='comercio'` y aparece en la serie en ≤ 60 s sin borrar la anterior.
- Prueba de `dudoso` marcado y `rechazado` excluido.
- Prueba de ausencia de campos prohibidos en la respuesta.
- Prueba de estado vacío, datos demo y truncado.
- Medición de p95 de la consulta de 90 días con 100 puntos.
- Cobertura ≥ 95 % del módulo puro de reglas de serie.
