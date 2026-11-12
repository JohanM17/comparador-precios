-- Migración 0002: Catálogo Normalizado, Establecimientos y Parámetros de Negocio
-- Basada estrictamente en la Sección 4.2 de docs/PLAN_CONSTRUCCION.md

create type rol_usuario as enum ('reportante', 'comercio', 'moderador');
create type estado_cuenta as enum ('activa', 'suspendida', 'bloqueada', 'eliminada');
create type unidad_base as enum ('g', 'ml', 'unidad');
create type unidad_entrada as enum ('g', 'kg', 'lb', 'ml', 'l', 'unidad', 'docena');
create type tipo_establecimiento as enum ('tienda_barrio', 'minimercado', 'supermercado', 'cadena');
create type estado_verificacion as enum ('sin_dueno', 'pendiente', 'verificado');
create type fuente_precio as enum ('usuario', 'comercio', 'semilla');
create type estado_confianza as enum ('aceptado', 'dudoso', 'rechazado');
create type sello_precio as enum ('confiable', 'pocos_datos', 'dudoso', 'desactualizado', 'oficial', 'en_disputa');
create type tipo_caso as enum ('reporte_dudoso', 'rafaga', 'solicitud_correccion', 'sugerencia_presentacion', 'verificacion_comercio', 'disputa_precio');
create type estado_caso as enum ('abierto', 'en_revision', 'resuelto');
create type decision_caso as enum ('confirmar', 'descartar', 'sancionar');
create type tipo_sancion as enum ('advertencia', 'suspension', 'bloqueo');

create table categoria (
  id smallint primary key,
  nombre text not null unique check (char_length(nombre) between 2 and 80),
  padre_id smallint references categoria(id),
  orden smallint not null default 0
);
alter table categoria enable row level security;

create table producto (
  id uuid primary key default gen_random_uuid(),
  nombre text not null unique check (char_length(nombre) between 2 and 120),
  nombre_norm text not null,
  categoria_id smallint not null references categoria(id),
  unidad_base unidad_base not null,
  imagen_url text check (imagen_url is null or char_length(imagen_url) <= 500),
  activo boolean not null default true,
  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);
alter table producto enable row level security;
create trigger trg_producto_actualizado before update on producto
for each row execute function actualizar_columna_timestamp();

create table presentacion (
  id uuid primary key default gen_random_uuid(),
  producto_id uuid not null references producto(id),
  marca text check (marca is null or char_length(marca) between 1 and 80),
  valor_cantidad numeric(12,3) not null check (valor_cantidad > 0),
  unidad unidad_entrada not null,
  multiplicador smallint not null default 1 check (multiplicador >= 1),
  cantidad_base numeric(14,3) not null check (cantidad_base > 0),
  etiqueta text not null check (char_length(etiqueta) between 3 and 180),
  etiqueta_norm text not null,
  codigo_barras text unique check (codigo_barras is null or codigo_barras ~ '^[0-9]{8,14}$'),
  fuente_catalogo text not null default 'manual' check (fuente_catalogo in ('manual', 'semilla', 'open_food_facts')),
  activa boolean not null default true,
  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now(),
  unique nulls not distinct (producto_id, marca, cantidad_base)
);
alter table presentacion enable row level security;
create trigger trg_presentacion_actualizado before update on presentacion
for each row execute function actualizar_columna_timestamp();

create table alias_producto (
  id uuid primary key default gen_random_uuid(),
  producto_id uuid not null references producto(id) on delete cascade,
  alias text not null check (char_length(alias) between 2 and 120),
  alias_norm text not null,
  unique (producto_id, alias_norm)
);
alter table alias_producto enable row level security;

create table establecimiento (
  id uuid primary key default gen_random_uuid(),
  nombre text not null check (char_length(nombre) between 2 and 120),
  tipo tipo_establecimiento not null,
  cadena text check (cadena is null or char_length(cadena) <= 80),
  direccion text not null check (char_length(direccion) between 3 and 200),
  barrio text check (barrio is null or char_length(barrio) <= 80),
  municipio text not null default 'Armenia' check (char_length(municipio) <= 80),
  departamento text not null default 'Quindío' check (char_length(departamento) <= 80),
  ubicacion geography(Point, 4326) not null,
  osm_id bigint,
  comercio_id uuid,
  estado_verificacion estado_verificacion not null default 'sin_dueno',
  activo boolean not null default true,
  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now(),
  unique (nombre, direccion)
);
alter table establecimiento enable row level security;
create trigger trg_establecimiento_actualizado before update on establecimiento
for each row execute function actualizar_columna_timestamp();

create table config_parametro (
  clave text primary key check (char_length(clave) between 3 and 80),
  valor jsonb not null,
  descripcion text not null check (char_length(descripcion) <= 300),
  actualizado_por uuid,
  actualizado_en timestamptz not null default now()
);
alter table config_parametro enable row level security;

create index idx_producto_nombre_trgm on producto using gin (nombre_norm gin_trgm_ops);
create index idx_presentacion_etiqueta_trgm on presentacion using gin (etiqueta_norm gin_trgm_ops);
create index idx_alias_producto_trgm on alias_producto using gin (alias_norm gin_trgm_ops);
create index idx_presentacion_producto on presentacion (producto_id) where activa = true;
create index idx_establecimiento_ubicacion on establecimiento using gist (ubicacion);
create index idx_establecimiento_municipio on establecimiento (municipio, activo);

-- Semilla de las 10 categorías base
insert into categoria (id, nombre, padre_id, orden) values
  (1, 'Granos, arroz y pastas', null, 1),
  (2, 'Lácteos y huevos', null, 2),
  (3, 'Aceites, sal y endulzantes', null, 3),
  (4, 'Café, chocolate y bebidas', null, 4),
  (5, 'Harinas, panadería y arepas', null, 5),
  (6, 'Enlatados y conservas', null, 6),
  (7, 'Carnes, pollo y embutidos', null, 7),
  (8, 'Frutas, verduras y tubérculos', null, 8),
  (9, 'Aseo del hogar', null, 9),
  (10, 'Cuidado personal', null, 10)
on conflict (id) do nothing;

-- Semilla obligatoria de los 43 parámetros de negocio
insert into config_parametro (clave, valor, descripcion) values
  ('precio.min_cop', '50'::jsonb, 'Precio mínimo aceptado en COP'),
  ('precio.max_cop', '2000000'::jsonb, 'Precio máximo aceptado en COP'),
  ('precio.ratio_extremo', '5.0'::jsonb, 'Multiplicador o divisor respecto a la mediana para señal ratio_extremo'),
  ('observado.max_antiguedad_horas', '24'::jsonb, 'Horas máximas hacia atrás permitidas en observado_en'),
  ('vigencia.fresco_horas', '48'::jsonb, 'Horas durante las cuales el reporte conserva factor temporal 1.0'),
  ('vigencia.vida_media_horas', '72'::jsonb, 'Horas para reducir el peso del reporte a la mitad'),
  ('vigencia.vigente_dias', '7'::jsonb, 'Días máximos para considerar vigente un reporte de usuario'),
  ('vigencia.antiguo_dias', '30'::jsonb, 'Días máximos para mostrar un reporte como desactualizado'),
  ('vigencia.comercio_revalidar_dias', '30'::jsonb, 'Días sin cambios para marcar precio oficial como por revalidar'),
  ('anomalia.ventana_dias', '14'::jsonb, 'Días de antigüedad máxima de los reportes del conjunto de referencia'),
  ('anomalia.n_min_referencia', '3'::jsonb, 'Mínimo de reportes aceptados para usar un nivel de referencia'),
  ('anomalia.n_min_z', '5'::jsonb, 'Mínimo de reportes para usar z-score modificado'),
  ('anomalia.z_umbral', '3.5'::jsonb, 'Umbral absoluto del z-score modificado'),
  ('anomalia.desviacion_pct_umbral', '0.30'::jsonb, 'Umbral de desviación porcentual cuando n < 5 o MAD = 0'),
  ('riesgo.pesos', '{"sin_foto":0.15,"cuenta_nueva":0.25,"rafaga":0.40,"reputacion_baja":0.20}'::jsonb, 'Pesos de las 4 señales de contexto'),
  ('riesgo.umbral_dudoso', '0.60'::jsonb, 'Puntaje de riesgo de contexto para marcar reporte como dudoso'),
  ('cuenta_nueva.dias', '7'::jsonb, 'Días desde creación para considerar cuenta nueva'),
  ('cuenta_nueva.min_aceptados', '3'::jsonb, 'Reportes corroborados mínimos para dejar de ser cuenta nueva'),
  ('reputacion.inicial', '0.500'::jsonb, 'Reputación inicial de todo perfil nuevo'),
  ('reputacion.baja_umbral', '0.350'::jsonb, 'Umbral por debajo del cual se activa reputacion_baja'),
  ('reputacion.corroboracion_tolerancia', '0.10'::jsonb, 'Tolerancia porcentual para considerar corroborado un reporte'),
  ('rafaga.ventana_min', '30'::jsonb, 'Ventana en minutos para detectar ráfaga por huella de red'),
  ('rafaga.min_cuentas', '3'::jsonb, 'Cuentas distintas mínimas con igual huella hacia la misma tienda'),
  ('sello.n_min_validos', '3'::jsonb, 'Mínimo de reportes vigentes para otorgar sello confiable'),
  ('sello.min_fuentes', '2'::jsonb, 'Mínimo de fuentes distintas para otorgar sello confiable'),
  ('sello.dispersion_max', '0.15'::jsonb, 'Dispersión máxima MAD/mediana permitida para sello confiable'),
  ('peso.con_foto', '1.2'::jsonb, 'Multiplicador del peso cuando el reporte incluye foto de prueba'),
  ('cache.ttl_segundos', '60'::jsonb, 'Tiempo máximo de vida en caché de comparación (EC-02)'),
  ('cache.l1_segundos', '5'::jsonb, 'Tiempo de vida en caché L1 de memoria'),
  ('limite.reportes_hora_nuevo', '20'::jsonb, 'Máximo de reportes por hora para cuenta nueva'),
  ('limite.reportes_hora_normal', '60'::jsonb, 'Máximo de reportes por hora para cuenta establecida'),
  ('limite.reportes_dia', '200'::jsonb, 'Máximo de reportes por día por usuario'),
  ('limite.consultas_ip_min', '120'::jsonb, 'Máximo de lecturas públicas por minuto por IP'),
  ('limite.escrituras_ip_min', '20'::jsonb, 'Máximo de escrituras por minuto por IP'),
  ('limite.correcciones_ip_dia', '3'::jsonb, 'Máximo de solicitudes de corrección de tienda por día por IP'),
  ('limite.fotos_hora_usuario', '30'::jsonb, 'Máximo de URLs firmadas de subida de foto por hora por usuario'),
  ('foto.max_kb', '300'::jsonb, 'Tamaño máximo de archivo de foto de prueba en KB'),
  ('foto.tipos', '["image/webp","image/jpeg"]'::jsonb, 'Tipos MIME aceptados para fotografías de prueba'),
  ('huella.retencion_dias', '30'::jsonb, 'Días de retención de huella_red antes de su anulación'),
  ('comparacion.radio_km', '10.0'::jsonb, 'Radio espacial por defecto en km para filtrar por cercanía'),
  ('comparacion.max_resultados', '50'::jsonb, 'Cantidad máxima de establecimientos devueltos en comparación'),
  ('disputa.min_reportes_y_cuentas', '{"min_reportes":3,"min_cuentas":2}'::jsonb, 'Mínimo de reportes y cuentas para declarar disputa con precio oficial'),
  ('disputa.ventana_y_diferencia', '{"ventana_horas":48,"diferencia_pct":0.10}'::jsonb, 'Ventana de horas y diferencia porcentual para declarar disputa')
on conflict (clave) do nothing;

