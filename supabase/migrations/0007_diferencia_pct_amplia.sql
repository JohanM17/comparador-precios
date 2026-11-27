-- Migración 0007: ampliar `precio_vigente.diferencia_pct`
--
-- La columna nació en 0006 como numeric(6,4), suficiente para diferencias
-- porcentuales de hasta 99,9999 %. El contraste D-01 compara dos precios en
-- pesos, no dos porcentajes: un precio oficial de $1.000 frente a una mediana
-- comunitaria de $200.000 produce 199,0000, que no cabe en la escala original
-- y hace fallar el UPSERT con "numeric field overflow".
--
-- numeric(14,4) conserva los cuatro decimales de precisión y amplía la parte
-- entera a diez dígitos, de modo que cualquier precio válido del dominio
-- (entero positivo en pesos) cabe sin desbordar. La migración es aditiva: no
-- renombra ni elimina columnas, solo ensancha una columna anulable.
--
-- Debe aplicarse con scripts/migrar.py antes de desplegar el código que persiste
-- contrastes con diferencias grandes; T-68 la validó en la base aislada.

alter table public.precio_vigente
  alter column diferencia_pct type numeric(14,4);
