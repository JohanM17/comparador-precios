-- Migración 0005: Historial de Precios (A2)
-- Índice aditivo que soporta la serie histórica por producto y establecimiento.
-- No crea ni altera tablas, columnas ni datos.

create index if not exists idx_reporte_historial_serie
  on public.reporte_precio (producto_id, establecimiento_id, observado_en desc)
  where estado in ('aceptado', 'dudoso');
