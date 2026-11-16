-- Migración 0003: Cuentas, Precios Inmutables, Moderación y Auditoría
-- Basada estrictamente en la Sección 4.3 de docs/PLAN_CONSTRUCCION.md

create table perfil (
  id uuid primary key,
  alias text not null unique check (char_length(alias) between 3 and 30 and alias ~ '^[a-zA-Z0-9_.-]+$'),
  rol rol_usuario not null default 'reportante',
  estado estado_cuenta not null default 'activa',
  suspendida_hasta timestamptz,
  reputacion numeric(4,3) not null default 0.500 check (reputacion between 0 and 1),
  reportes_corroborados int not null default 0 check (reportes_corroborados >= 0),
  reportes_malos_confirmados int not null default 0 check (reportes_malos_confirmados >= 0),
  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);
alter table perfil enable row level security;
create trigger trg_perfil_actualizado before update on perfil
for each row execute function actualizar_columna_timestamp();

alter table establecimiento
  add constraint fk_establecimiento_comercio foreign key (comercio_id) references perfil(id) on delete set null;

create table autorizacion_datos (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references perfil(id) on delete cascade,
  version_politica text not null check (char_length(version_politica) <= 20),
  finalidad text not null check (char_length(finalidad) between 20 and 2000),
  aceptada_en timestamptz not null default now(),
  revocada_en timestamptz
);
alter table autorizacion_datos enable row level security;

create table sancion (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references perfil(id),
  tipo tipo_sancion not null,
  motivo text not null check (char_length(motivo) between 5 and 500),
  desde timestamptz not null default now(),
  hasta timestamptz,
  moderador_id uuid not null references perfil(id),
  apelacion text check (apelacion is null or char_length(apelacion) <= 1000),
  apelacion_resuelta boolean
);
alter table sancion enable row level security;

create table sugerencia_presentacion (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid references perfil(id) on delete set null,
  producto_id uuid references producto(id),
  texto_libre text not null check (char_length(texto_libre) between 3 and 200),
  marca text check (marca is null or char_length(marca) <= 80),
  valor_cantidad numeric(12,3) check (valor_cantidad is null or valor_cantidad > 0),
  unidad unidad_entrada,
  codigo_barras text check (codigo_barras is null or codigo_barras ~ '^[0-9]{8,14}$'),
  estado text not null default 'pendiente' check (estado in ('pendiente', 'aprobada', 'rechazada')),
  creado_en timestamptz not null default now()
);
alter table sugerencia_presentacion enable row level security;

create table reporte_precio (
  id uuid primary key default gen_random_uuid(),
  presentacion_id uuid not null references presentacion(id),
  establecimiento_id uuid not null references establecimiento(id),
  producto_id uuid not null references producto(id),
  precio_cop integer not null check (precio_cop > 0),
  incluye_impuestos boolean not null default true check (incluye_impuestos = true),
  cantidad_base_snapshot numeric(14,3) not null check (cantidad_base_snapshot > 0),
  precio_por_base numeric(14,6) not null check (precio_por_base > 0),
  fuente fuente_precio not null,
  reportante_id uuid references perfil(id) on delete set null,
  observado_en timestamptz not null,
  foto_prueba_path text check (foto_prueba_path is null or char_length(foto_prueba_path) <= 300),
  estado estado_confianza not null,
  estado_original estado_confianza not null,
  senales text[] not null default '{}',
  puntaje_anomalia numeric(8,3),
  riesgo_contexto numeric(4,3) not null default 0 check (riesgo_contexto between 0 and 1),
  conjunto_referencia text not null check (conjunto_referencia in ('presentacion_tienda', 'presentacion', 'producto_unitario', 'sin_referencia')),
  huella_red text check (huella_red is null or char_length(huella_red) = 64),
  idempotency_key uuid,
  es_demo boolean not null default false,
  revisado_por uuid references perfil(id),
  revisado_en timestamptz,
  creado_en timestamptz not null default now(),
  unique (reportante_id, idempotency_key)
);
alter table reporte_precio enable row level security;

create or replace function bloquear_cambios_reporte()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'PROHIBIDO_BORRAR_REPORTE: La tabla reporte_precio es inmutable.';
  end if;

  if new.id <> old.id
     or new.presentacion_id <> old.presentacion_id
     or new.establecimiento_id <> old.establecimiento_id
     or new.producto_id <> old.producto_id
     or new.precio_cop <> old.precio_cop
     or new.cantidad_base_snapshot <> old.cantidad_base_snapshot
     or new.precio_por_base <> old.precio_por_base
     or new.fuente <> old.fuente
     or new.observado_en <> old.observado_en
     or new.estado_original <> old.estado_original
     or new.es_demo <> old.es_demo
     or new.creado_en <> old.creado_en then
    raise exception 'PROHIBIDO_MODIFICAR_REPORTE: Los campos de evidencia del reporte son inmutables.';
  end if;

  if old.reportante_id is not null and new.reportante_id is not null and new.reportante_id <> old.reportante_id then
    raise exception 'PROHIBIDO_CAMBIAR_AUTOR: Solo se permite anonimizar reportante_id a NULL.';
  end if;

  return new;
end;
$$;

create trigger trg_inmutabilidad_reporte
before update or delete on reporte_precio
for each row execute function bloquear_cambios_reporte();

create table precio_vigente (
  presentacion_id uuid not null references presentacion(id),
  establecimiento_id uuid not null references establecimiento(id),
  producto_id uuid not null references producto(id),
  precio_cop integer not null check (precio_cop > 0),
  precio_por_base numeric(14,6) not null check (precio_por_base > 0),
  cantidad_base numeric(14,3) not null check (cantidad_base > 0),
  sello sello_precio not null,
  motivo_sello text check (motivo_sello is null or char_length(motivo_sello) <= 200),
  n_reportes_validos smallint not null check (n_reportes_validos >= 0),
  n_fuentes smallint not null check (n_fuentes >= 0),
  dispersion numeric(6,4),
  ultimo_reporte_en timestamptz not null,
  reporte_origen_id uuid references reporte_precio(id),
  recalculado_en timestamptz not null default now(),
  primary key (presentacion_id, establecimiento_id)
);
alter table precio_vigente enable row level security;

create table caso_moderacion (
  id uuid primary key default gen_random_uuid(),
  tipo tipo_caso not null,
  referencia_tabla text not null check (char_length(referencia_tabla) <= 60),
  referencia_id uuid,
  detalle jsonb not null default '{}',
  prioridad smallint not null default 3 check (prioridad between 1 and 5),
  estado estado_caso not null default 'abierto',
  decision decision_caso,
  moderador_id uuid references perfil(id),
  nota text check (nota is null or char_length(nota) <= 1000),
  creado_en timestamptz not null default now(),
  resuelto_en timestamptz
);
alter table caso_moderacion enable row level security;

create table auditoria (
  id bigserial primary key,
  actor_id uuid,
  rol text,
  accion text not null check (char_length(accion) <= 100),
  entidad text not null check (char_length(entidad) <= 60),
  entidad_id text,
  antes jsonb,
  despues jsonb,
  creado_en timestamptz not null default now()
);
alter table auditoria enable row level security;

revoke update, delete on auditoria from app_backend;
revoke delete on reporte_precio from app_backend;

create index idx_reporte_par_observado on reporte_precio (presentacion_id, establecimiento_id, observado_en desc) where estado = 'aceptado';
create index idx_reporte_rafaga on reporte_precio (establecimiento_id, huella_red, creado_en desc) where huella_red is not null;
create index idx_reporte_autor on reporte_precio (reportante_id, creado_en desc);
create index idx_reporte_producto_fecha on reporte_precio (producto_id, observado_en desc);
create index idx_precio_vigente_producto on precio_vigente (producto_id, sello, precio_por_base);
create index idx_caso_moderacion_cola on caso_moderacion (estado, prioridad asc, creado_en asc);

