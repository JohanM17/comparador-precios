-- Roles que Supabase trae de fabrica y Postgres a secas no.
--
-- La migracion 0001 les revoca privilegios sobre el esquema publico (ADR-012).
-- Sin estos roles esa sentencia falla y ninguna migracion aplica, asi que la
-- base de pruebas tiene que parecerse a Supabase al menos en esto.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
end
$$;
