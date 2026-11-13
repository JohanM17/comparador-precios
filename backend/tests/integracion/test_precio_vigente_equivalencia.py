"""Pruebas de integracion para equivalencia matematica de precio_vigente (T-24)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.puertos.politica_precio import SoloUsuarios, reconstruir_precio_vigente


@pytest.mark.asyncio
async def test_equivalencia_incremental_vs_reconstruccion_completa() -> None:
    """Verifica que recalcular incrementalmente sea 100% equivalente a reconstruir desde cero."""
    instante = datetime.now(UTC)
    politica = SoloUsuarios()

    async with sesion_transaccional() as sesion:
        # 1. Obtener dos presentaciones y dos establecimientos
        pres_rows = (
            await sesion.execute(text("SELECT id, producto_id FROM presentacion LIMIT 2;"))
        ).fetchall()
        est_rows = (
            await sesion.execute(text("SELECT id FROM establecimiento LIMIT 2;"))
        ).fetchall()
        assert len(pres_rows) >= 2
        assert len(est_rows) >= 2

        pres1, prod1 = pres_rows[0][0], pres_rows[0][1]
        pres2, prod2 = pres_rows[1][0], pres_rows[1][1]
        est1 = est_rows[0][0]
        est2 = est_rows[1][0]

        # 2. Insertar varios reportes aceptados con fechas recientes
        uid = str(uuid4())
        await sesion.execute(
            text("""
                INSERT INTO perfil (id, alias, rol, estado, reputacion)
                VALUES (:id, :alias, 'reportante', 'activa', 0.8)
                ON CONFLICT (id) DO NOTHING;
            """),
            {"id": uid, "alias": f"eq_{uid[:8]}"},
        )

        pares = [(pres1, est1, prod1, 2500), (pres1, est2, prod1, 2700), (pres2, est1, prod2, 4100)]

        for p_id, e_id, pr_id, precio in pares:
            sql_rep = text("""
                INSERT INTO reporte_precio (
                    producto_id, presentacion_id, establecimiento_id, precio_cop,
                    cantidad_base_snapshot, precio_por_base, observado_en,
                    estado, estado_original, fuente, conjunto_referencia,
                    reportante_id
                ) VALUES (
                    :prod_id, :pres_id, :est_id, :precio_cop,
                    1.000, :precio_por_base, :ahora,
                    'aceptado', 'aceptado', 'usuario', 'sin_referencia',
                    :uid
                );
            """)
            await sesion.execute(
                sql_rep,
                {
                    "prod_id": pr_id,
                    "pres_id": p_id,
                    "est_id": e_id,
                    "precio_cop": precio,
                    "precio_por_base": float(precio),
                    "ahora": instante,
                    "uid": uid,
                },
            )
            # Calculo incremental inmediato
            await politica.recalcular_par(sesion, p_id, e_id, instante)

        # 3. Snapshot de precio_vigente incremental para los pares evaluados
        ids_pres = list({p[0] for p in pares})
        sql_snap = text("""
            SELECT presentacion_id, establecimiento_id, precio_cop, precio_por_base, sello::text
            FROM precio_vigente
            WHERE presentacion_id = ANY(:pres_ids)
            ORDER BY presentacion_id, establecimiento_id;
        """)
        filas_incremental = (await sesion.execute(sql_snap, {"pres_ids": ids_pres})).fetchall()

        # 4. Ejecutar reconstruccion completa
        recalculados = await reconstruir_precio_vigente(sesion, ahora=instante, politica=politica)
        assert recalculados >= len(pares)

        # 5. Snapshot post-reconstruccion
        filas_reconstruido = (await sesion.execute(sql_snap, {"pres_ids": ids_pres})).fetchall()

        # 6. Comparar equivalencia exacta para los pares probados
        for p_id, e_id, _, _ in pares:
            f_inc = next(
                f
                for f in filas_incremental
                if f.presentacion_id == p_id and f.establecimiento_id == e_id
            )
            f_rec = next(
                f
                for f in filas_reconstruido
                if f.presentacion_id == p_id and f.establecimiento_id == e_id
            )
            assert f_inc.presentacion_id == f_rec.presentacion_id
            assert f_inc.establecimiento_id == f_rec.establecimiento_id
            assert f_inc.precio_cop == f_rec.precio_cop
            assert f_inc.precio_por_base == f_rec.precio_por_base
            assert f_inc.sello == f_rec.sello
            assert f_inc.sello == f_rec.sello
