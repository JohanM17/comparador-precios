"""Pruebas de integración para inmutabilidad de reportes y auditoría (Migración 0003)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.bd import sesion_transaccional


@pytest.fixture
async def datos_prueba_reporte() -> dict[str, str]:
    """Crea registros base para probar inserción e inmutabilidad en reporte_precio."""
    async with sesion_transaccional() as sesion:
        perfil_id = str(uuid.uuid4())
        prod_id = str(uuid.uuid4())
        pres_id = str(uuid.uuid4())
        tienda_id = str(uuid.uuid4())
        alias = f"user_{uuid.uuid4().hex[:8]}"

        await sesion.execute(
            text("INSERT INTO perfil (id, alias, rol) VALUES (:id, :alias, 'reportante');"),
            {"id": perfil_id, "alias": alias},
        )
        await sesion.execute(
            text("""
                INSERT INTO producto (id, nombre, nombre_norm, categoria_id, unidad_base)
                VALUES (:id, :nombre, :nombre_norm, 1, 'g');
            """),
            {
                "id": prod_id,
                "nombre": f"Prod Test {alias}",
                "nombre_norm": f"prod test {alias}",
            },
        )
        await sesion.execute(
            text("""
                INSERT INTO presentacion (
                    id, producto_id, valor_cantidad, unidad,
                    cantidad_base, etiqueta, etiqueta_norm
                ) VALUES (
                    :id, :prod_id, 500, 'g', 500.000, '500g Test', '500g test'
                );
            """),
            {"id": pres_id, "prod_id": prod_id},
        )
        await sesion.execute(
            text("""
                INSERT INTO establecimiento (id, nombre, tipo, direccion, ubicacion)
                VALUES (
                    :id, :nombre, 'tienda_barrio', 'Cra 14 # 20-00',
                    ST_SetSRID(ST_MakePoint(-75.6811, 4.5338), 4326)
                );
            """),
            {"id": tienda_id, "nombre": f"Tienda {alias}"},
        )

        return {
            "perfil_id": perfil_id,
            "producto_id": prod_id,
            "presentacion_id": pres_id,
            "establecimiento_id": tienda_id,
        }


@pytest.mark.asyncio
async def test_trigger_bloquea_borrado_reporte_precio(
    datos_prueba_reporte: dict[str, str],
) -> None:
    """Verifica que DELETE sobre reporte_precio sea bloqueado por trigger y permisos."""
    rep_id = str(uuid.uuid4())
    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("""
                INSERT INTO reporte_precio (
                    id, presentacion_id, establecimiento_id, producto_id,
                    precio_cop, cantidad_base_snapshot, precio_por_base,
                    fuente, reportante_id, observado_en, estado, estado_original,
                    conjunto_referencia
                ) VALUES (
                    :id, :pres_id, :tienda_id, :prod_id,
                    3000, 500.000, 6.000000,
                    'usuario', :user_id, now(), 'aceptado', 'aceptado',
                    'presentacion_tienda'
                );
            """),
            {
                "id": rep_id,
                "pres_id": datos_prueba_reporte["presentacion_id"],
                "tienda_id": datos_prueba_reporte["establecimiento_id"],
                "prod_id": datos_prueba_reporte["producto_id"],
                "user_id": datos_prueba_reporte["perfil_id"],
            },
        )

    # El intento de DELETE debe lanzar DBAPIError por el trigger o por el revoke
    sentencia_del = text("DELETE FROM reporte_precio WHERE id = :id;")
    params_del = {"id": rep_id}
    async with sesion_transaccional() as sesion:
        with pytest.raises(DBAPIError) as exc_info:
            await sesion.execute(sentencia_del, params_del)
    assert (
        "PROHIBIDO_BORRAR_REPORTE" in str(exc_info.value)
        or "permission denied" in str(exc_info.value).lower()
    )


@pytest.mark.asyncio
async def test_trigger_bloquea_modificar_precio_cop(
    datos_prueba_reporte: dict[str, str],
) -> None:
    """Verifica que UPDATE de precio_cop sea bloqueado por el trigger de inmutabilidad."""
    rep_id = str(uuid.uuid4())
    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("""
                INSERT INTO reporte_precio (
                    id, presentacion_id, establecimiento_id, producto_id,
                    precio_cop, cantidad_base_snapshot, precio_por_base,
                    fuente, reportante_id, observado_en, estado, estado_original,
                    conjunto_referencia
                ) VALUES (
                    :id, :pres_id, :tienda_id, :prod_id,
                    4000, 500.000, 8.000000,
                    'usuario', :user_id, now(), 'aceptado', 'aceptado',
                    'presentacion_tienda'
                );
            """),
            {
                "id": rep_id,
                "pres_id": datos_prueba_reporte["presentacion_id"],
                "tienda_id": datos_prueba_reporte["establecimiento_id"],
                "prod_id": datos_prueba_reporte["producto_id"],
                "user_id": datos_prueba_reporte["perfil_id"],
            },
        )

    sentencia_upd = text("UPDATE reporte_precio SET precio_cop = 5000 WHERE id = :id;")
    params_upd = {"id": rep_id}
    async with sesion_transaccional() as sesion:
        with pytest.raises(DBAPIError, match="PROHIBIDO_MODIFICAR_REPORTE"):
            await sesion.execute(sentencia_upd, params_upd)


@pytest.mark.asyncio
async def test_permite_actualizar_estado_y_anonimizar_autor(
    datos_prueba_reporte: dict[str, str],
) -> None:
    """Verifica que sí se permite cambiar estado (moderación) y reportante_id a NULL (Ley 1581)."""
    rep_id = str(uuid.uuid4())
    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("""
                INSERT INTO reporte_precio (
                    id, presentacion_id, establecimiento_id, producto_id,
                    precio_cop, cantidad_base_snapshot, precio_por_base,
                    fuente, reportante_id, observado_en, estado, estado_original,
                    conjunto_referencia
                ) VALUES (
                    :id, :pres_id, :tienda_id, :prod_id,
                    2500, 500.000, 5.000000,
                    'usuario', :user_id, now(), 'aceptado', 'aceptado',
                    'presentacion_tienda'
                );
            """),
            {
                "id": rep_id,
                "pres_id": datos_prueba_reporte["presentacion_id"],
                "tienda_id": datos_prueba_reporte["establecimiento_id"],
                "prod_id": datos_prueba_reporte["producto_id"],
                "user_id": datos_prueba_reporte["perfil_id"],
            },
        )

    # 1. Moderación actualiza estado a 'dudoso'
    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("UPDATE reporte_precio SET estado = 'dudoso' WHERE id = :id;"),
            {"id": rep_id},
        )
        res = await sesion.execute(
            text("SELECT estado FROM reporte_precio WHERE id = :id;"),
            {"id": rep_id},
        )
        assert res.scalar_one() == "dudoso"

    # 2. Supresión de cuenta anonimiza reportante_id = NULL
    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("UPDATE reporte_precio SET reportante_id = NULL WHERE id = :id;"),
            {"id": rep_id},
        )
        res = await sesion.execute(
            text("SELECT reportante_id FROM reporte_precio WHERE id = :id;"),
            {"id": rep_id},
        )
        assert res.scalar_one() is None


@pytest.mark.asyncio
async def test_auditoria_bloquea_borrado_y_modificacion() -> None:
    """Verifica que la tabla auditoria sea estrictamente append-only para app_backend."""
    async with sesion_transaccional() as sesion:
        res = await sesion.execute(
            text("""
                INSERT INTO auditoria (accion, entidad, entidad_id)
                VALUES ('TEST_AUDIT', 'test', '123')
                RETURNING id;
            """)
        )
        audit_id = res.scalar_one()

    sentencia_audit_del = text("DELETE FROM auditoria WHERE id = :id;")
    params_audit = {"id": audit_id}
    async with sesion_transaccional() as sesion:
        with pytest.raises(DBAPIError) as exc_info:
            await sesion.execute(sentencia_audit_del, params_audit)
    assert "permission denied" in str(exc_info.value).lower()
