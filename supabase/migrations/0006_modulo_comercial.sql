-- Migración 0006: Módulo Comercial (Etapa 2)
--
-- Lleva el número 0006 y no 0004 porque la ampliación A2 aplicó primero
-- 0005_historial_precios.sql sobre la base compartida. Una migración no se
-- intercala por debajo de otra ya aplicada: el orden del archivo dejaría de
-- coincidir con el orden real de _migraciones_historial.
-- Basada en la Sección 4.4 de docs/PLAN_CONSTRUCCION.md (tarea T-61).
--
-- Migración ADITIVA: no altera ni elimina ninguna columna del núcleo.
-- Los enumerados sello_precio (oficial, en_disputa), tipo_caso (verificacion_comercio,
-- disputa_precio), estado_verificacion y fuente_precio ya existen desde 0002, igual que
-- la columna anulable establecimiento.comercio_id y los parámetros de disputa de D-01.

create type tipo_promocion as enum ('porcentaje', 'precio_especial', 'pague_x_lleve_y');

-- D-09: un usuario reclama la titularidad de un establecimiento y un moderador humano decide.
create table solicitud_verificacion_comercio (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references perfil(id) on delete cascade,
  establecimiento_id uuid not null references establecimiento(id),
  telefono_contacto text not null check (char_length(telefono_contacto) between 7 and 30),
  mensaje text not null check (char_length(mensaje) between 5 and 500),
  estado estado_verificacion not null default 'pendiente',
  verificado_por uuid references perfil(id),
  verificado_en timestamptz,
  creado_en timestamptz not null default now()
);
alter table solicitud_verificacion_comercio enable row level security;

-- Un establecimiento no puede tener dos reclamos abiertos a la vez.
create unique index uq_solicitud_verificacion_abierta
  on solicitud_verificacion_comercio (establecimiento_id)
  where estado = 'pendiente';

create index idx_solicitud_verificacion_cola
  on solicitud_verificacion_comercio (estado, creado_en asc);

-- FR-022: precio publicado por el comercio dueño del establecimiento.
create table precio_oficial (
  presentacion_id uuid not null references presentacion(id),
  establecimiento_id uuid not null references establecimiento(id),
  producto_id uuid not null references producto(id),
  comercio_id uuid not null references perfil(id),
  precio_cop integer not null check (precio_cop > 0),
  precio_por_base numeric(14,6) not null check (precio_por_base > 0),
  actualizado_en timestamptz not null default now(),
  revalidado_en timestamptz not null default now(),
  activo boolean not null default true,
  primary key (presentacion_id, establecimiento_id)
);
alter table precio_oficial enable row level security;

create index idx_precio_oficial_establecimiento
  on precio_oficial (establecimiento_id, activo, revalidado_en desc);
create index idx_precio_oficial_comercio on precio_oficial (comercio_id);

-- FR-024: toda promoción declara condiciones de tiempo, modo y lugar (Ley 1480 art. 33).
create table promocion (
  id uuid primary key default gen_random_uuid(),
  establecimiento_id uuid not null references establecimiento(id),
  producto_id uuid not null references producto(id),
  presentacion_id uuid references presentacion(id),
  comercio_id uuid not null references perfil(id),
  titulo text not null check (char_length(titulo) between 5 and 120),
  tipo tipo_promocion not null,
  porcentaje_descuento smallint check (porcentaje_descuento is null or porcentaje_descuento between 1 and 90),
  precio_especial_cop integer check (precio_especial_cop is null or precio_especial_cop > 0),
  pague_x smallint check (pague_x is null or pague_x >= 1),
  lleve_y smallint check (lleve_y is null or lleve_y >= 2),
  condiciones text not null check (char_length(condiciones) between 10 and 500),
  vigente_desde timestamptz not null,
  vigente_hasta timestamptz,
  hasta_revocar boolean not null default false,
  revocada_en timestamptz,
  activa boolean not null default true,
  creado_en timestamptz not null default now(),
  constraint ck_promocion_vigencia
    check ((vigente_hasta is not null and hasta_revocar = false)
        or (vigente_hasta is null and hasta_revocar = true)),
  constraint ck_promocion_lleve_mayor
    check (pague_x is null or lleve_y > pague_x),
  -- Cada tipo exige sus campos y prohíbe los de los otros: el tipo y los datos no pueden mentir.
  constraint ck_promocion_campos_por_tipo check (
    (tipo = 'porcentaje'
      and porcentaje_descuento is not null
      and precio_especial_cop is null and pague_x is null and lleve_y is null)
    or (tipo = 'precio_especial'
      and precio_especial_cop is not null
      and porcentaje_descuento is null and pague_x is null and lleve_y is null)
    or (tipo = 'pague_x_lleve_y'
      and pague_x is not null and lleve_y is not null
      and porcentaje_descuento is null and precio_especial_cop is null)
  )
);
alter table promocion enable row level security;

create index idx_promocion_producto_vigente
  on promocion (producto_id, activa, vigente_desde desc);
create index idx_promocion_establecimiento on promocion (establecimiento_id, activa);

-- Columnas aditivas del contraste D-01. El núcleo no pierde ninguna columna.
alter table precio_vigente
  add column if not exists precio_oficial_cop integer,
  add column if not exists diferencia_pct numeric(6,4),
  add column if not exists requiere_revalidacion boolean not null default false;
