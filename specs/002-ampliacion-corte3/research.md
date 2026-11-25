# Research — Ampliación Corte 3 (A2 + B1)

**Feature**: `002-ampliacion-corte3` | **Date**: 2026-11-25

Este documento resuelve las incógnitas técnicas del plan. Las decisiones estructurales se registran en `ADR-0019` y `ADR-0020`.

## A2 — Historial y tendencia de precios

### Decisión 1: fuente de la serie

- **Decisión**: usar `reporte_precio` (append-only) como fuente única de la serie; no introducir Event Sourcing ni una tabla `historial_precio` separada.
- **Razón**: la tabla ya conserva todas las observaciones con `observado_en`, `fuente`, `estado`, `precio_cop` y `precio_por_base`; es inmutable y está auditada. Event Sourcing añadiría infraestructura y duplicaría la fuente de verdad.
- **Alternativas consideradas**:
  - Event Sourcing completo: descartado por costo y complejidad.
  - Tabla de snapshots separada: descartada por sincronización y doble fuente de verdad.
- **Consecuencia**: el módulo comercial debe agregar cada cambio oficial a `reporte_precio` con `fuente='comercio'` (`T-63`).

### Decisión 2: granularidad de los puntos

- **Decisión**: devolver observaciones individuales ordenadas por `observado_en`, sin agregación diaria en el MVP; límite por defecto 200, máximo 500, con marca `truncado`.
- **Razón**: el volumen esperado es bajo y la observación individual conserva la trazabilidad de origen y estado. La agregación puede añadirse después si el volumen lo exige.
- **Alternativas consideradas**:
  - Agregación diaria por mediana: útil para gráficas densas, pero pierde la observación individual y complica la regla de confiabilidad.
  - Agregación semanal: reduce puntos, pero oculta cambios relevantes.
- **Consecuencia**: el frontend debe manejar hasta 500 puntos y mostrar un aviso si la serie está truncada.

### Decisión 3: estados incluidos

- **Decisión**: incluir `aceptado` y `dudoso`; excluir `rechazado` como precio histórico válido. Los `dudoso` se muestran con marca explícita.
- **Razón**: el anexo exige mostrar el estado de confiabilidad; ocultar los dudosos impide entender la serie, pero presentarlos como confiables sería engañoso. Los rechazados no son precios válidos.
- **Alternativas consideradas**:
  - Solo aceptados: serie más limpia, pero pierde la historia de revisión.
  - Incluir rechazados con marca: útil para auditoría, pero confuso para el consumidor; se puede añadir una vista de moderación futura.
- **Consecuencia**: la UI debe tener leyenda y patrón visual para `dudoso`.

### Decisión 4: origen y etiquetas

- **Decisión**: exponer `origen` como `usuario`, `comercio` o `semilla`; la UI etiqueta `usuario` = reportado, `comercio` = oficial, `semilla` = pública/demostración. `es_demo` se conserva por punto.
- **Razón**: el anexo pide distinguir oficial, reportado y fuente pública; el proyecto ya tiene esos valores en `fuente_precio`. No se inventa una fuente externa que no existe.
- **Alternativas consideradas**:
  - Añadir un valor `publica` al enum para SIPSA: se pospone hasta que exista una ingesta real; no se requiere para el mínimo.
  - Ocultar la semilla: perdería la distinción de origen y el aviso de demostración.
- **Consecuencia**: si en el futuro se ingesta SIPSA, se añade `publica` con una migración aditiva.

### Decisión 5: gráfica

- **Decisión**: usar `recharts` con carga dinámica en la ficha de producto y una tabla HTML alternativa con los mismos datos; auditoría axe.
- **Razón**: acelera la implementación, es compatible con React 18/Next 14 y permite series y tooltips; la tabla garantiza accesibilidad y sirve de respaldo.
- **Alternativas consideradas**:
  - SVG propio: control total y sin dependencia, pero más tiempo de desarrollo y pruebas.
  - Chart.js: buena opción, pero menos integrada con React.
- **Consecuencia**: añadir `recharts` a `package.json`; vigilar el tamaño del bundle con carga dinámica.

### Decisión 6: rendimiento y caché

- **Decisión**: consultar directamente PostgreSQL con índice compuesto; no cachear en el MVP. Si se añade caché, TTL ≤ 60 s e invalidación por producto.
- **Razón**: el volumen es bajo y `EC-08` exige que el cambio aparezca dentro del plazo de `EC-02`; una consulta directa es simple y correcta. El índice evita degradación.
- **Alternativas consideradas**:
  - Cachear la serie en L1/L2: reduce latencia, pero añade invalidación y riesgo de datos obsoletos.
  - Precalcular series: overkill para el volumen actual.
- **Consecuencia**: crear `0005_historial_precios.sql` con índice `(producto_id, establecimiento_id, observado_en)`.

## B1 — Observabilidad y SLO

### Decisión 7: backend de observabilidad

- **Decisión**: OpenTelemetry SDK + OTLP/HTTP a Grafana Cloud Free; alternativa de endpoint OTLP nativo del proveedor si la cuota no alcanza.
- **Razón**: estándar, portable, trazas/métricas/logs en un solo lugar, capa gratuita y configuración por variables. Evita autohospedar Tempo/Loki/Mimir.
- **Alternativas consideradas**:
  - Métricas nativas del proveedor: simples, pero sin trazas ni correlación suficiente para EC-11.
  - Stack autohospedado: control total, pero costo operativo y Docker, incompatible con el entorno local.
- **Consecuencia**: `PA-05` debe confirmar cuotas y retención; el código debe poder apuntar a otro endpoint OTLP sin cambios.

### Decisión 8: SLO y SLI

- **Decisión**: SLI = proporción de peticiones de comparación con latencia ≤ 2 s y sin 5xx; SLO 99,0 % en ventana móvil de 7 días; presupuesto de error 1,0 %.
- **Razón**: `EC-04` exige p95 ≤ 2 s y error < 1 %; el SLO traduce ese escenario a una medida operativa. La ventana de 7 días es adecuada para el corte y se puede ampliar a 30 días en producción.
- **Alternativas consideradas**:
  - SLO basado solo en errores: ignora la latencia, que es la experiencia principal del consumidor.
  - SLO basado solo en p95: no captura la proporción de usuarios afectados; se complementa con el panel de latencia.
- **Consecuencia**: el tablero debe mostrar SLI, meta, presupuesto consumido y estado de la alerta.

### Decisión 9: muestreo

- **Decisión**: 100 % de errores y 20 % de éxitos por defecto, configurable por `OTEL_TRACES_SAMPLER_ARG`; retención según la capa gratuita.
- **Razón**: conserva todas las fallas para diagnóstico y reduce costo/volumen de éxitos. El 20 % es suficiente para analizar latencia y trazas en una carga de prueba.
- **Alternativas consideradas**:
  - 100 % de todo: mayor fidelidad, pero más costo y ruido.
  - Muestreo aleatorio uniforme: puede perder errores; se usa un sampler por estado o una regla de errores al 100 %.
- **Consecuencia**: documentar cómo cambiar el muestreo y cómo verificar que los errores no se pierden.

### Decisión 10: privacidad de telemetría

- **Decisión**: lista de atributos prohibidos (`lat`, `lng`, `reportante_id`, alias, correo, IP, `huella_red`, `foto_prueba_path`, `authorization`) y lista de permitidos (ruta, método, estado, duración, `cache_hit`, `db_ms`, `resultados_count`, `estado`, `fuente`). Prueba automatizada con exportador en memoria.
- **Razón**: Ley 1581 y principio II; la telemetría no debe convertirse en un registro paralelo de datos personales.
- **Alternativas consideradas**:
  - Confiar en la revisión manual: insuficiente y no reproducible.
  - Anonimizar después: el dato sensible ya habría salido del perímetro.
- **Consecuencia**: cualquier atributo nuevo requiere revisión y prueba.

### Decisión 11: inyección de latencia

- **Decisión**: variable de entorno `SIMULAR_LATENCIA_MS` leída por un middleware de prueba, deshabilitada en producción y documentada; activa solo con `ENTORNO != production`.
- **Razón**: permite demostrar `EC-11` sin modificar el código de negocio ni desplegar una versión especial.
- **Alternativas consideradas**:
  - Toxiproxy/proxy externo: más realista, pero añade infraestructura.
  - Endpoint de prueba dedicado: contamina el contrato público.
- **Consecuencia**: el simulacro debe verificar que la variable no está activa en producción.

### Decisión 12: numeración de migraciones

- **Decisión**: `0005_historial_precios.sql` para el índice de A2; la migración de Fase 2 (`supervisor_ia`) pasa a `0006` cuando se implemente.
- **Razón**: el módulo comercial usa `0004`; la ampliación es el siguiente cambio. No se editan migraciones aplicadas.
- **Alternativas consideradas**:
  - `0004b`: evita renumerar, pero rompe la convención secuencial.
  - Incluir el índice en `0004`: mezcla cambios y edita una migración del módulo comercial.
- **Consecuencia**: actualizar la referencia de `0005_supervisor_ia.sql` a `0006` en el plan de Fase 2 cuando se aborde.

## Incógnitas abiertas

- **PA-05**: proveedor/cuotas de observabilidad.
- **PA-06**: mapeo de «Entregable 5/6» del anexo con la numeración global del proyecto.
- **Dependencia**: el módulo comercial debe conservar el historial del precio oficial (`T-63`).
- **Fuente pública**: no hay ingesta real de SIPSA; `semilla` se etiqueta como pública/demostración. Si el curso exige una fuente externa real, se evalúa después del mínimo.
