create extension if not exists postgis;
create extension if not exists pg_trgm;
create extension if not exists unaccent;
create extension if not exists pgcrypto;

-- Rol de aplicacion con LOGIN y privilegios minimos (cumple ADR-012)
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_backend') then
    create role app_backend with login password 'app_backend_local_pass';
  end if;
end
$$;

alter role app_backend bypassrls;
grant usage on schema public to app_backend;
grant app_backend to postgres;
revoke all on all tables in schema public from anon, authenticated;
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public grant select, insert, update, delete on tables to app_backend;
alter default privileges in schema public grant usage, select on sequences to app_backend;

create or replace function actualizar_columna_timestamp()
returns trigger
language plpgsql
as $$
begin
  new.actualizado_en = now();
  return new;
end;
$$;
