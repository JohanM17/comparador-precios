"""Repositorio de base de datos para perfiles, autorizaciones Ley 1581 y anonimizacion."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def verificar_alias_disponible(
    sesion: AsyncSession,
    alias: str,
    usuario_id: UUID | None = None,
) -> bool:
    """Verifica si un alias esta libre para ser usado por un usuario."""
    if usuario_id is not None:
        sql = text("SELECT 1 FROM perfil WHERE alias = :alias AND id <> :usuario_id LIMIT 1;")
        res = (await sesion.execute(sql, {"alias": alias, "usuario_id": usuario_id})).fetchone()
    else:
        sql = text("SELECT 1 FROM perfil WHERE alias = :alias LIMIT 1;")
        res = (await sesion.execute(sql, {"alias": alias})).fetchone()
    return res is None


async def obtener_autorizacion_vigente(
    sesion: AsyncSession,
    usuario_id: UUID,
) -> dict[str, Any] | None:
    """Obtiene el consentimiento activo no revocado del usuario."""
    sql = text("""
        SELECT id, version_politica, finalidad, aceptada_en
        FROM autorizacion_datos
        WHERE usuario_id = :uid AND revocada_en IS NULL
        ORDER BY aceptada_en DESC
        LIMIT 1;
    """)
    fila = (await sesion.execute(sql, {"uid": usuario_id})).fetchone()
    return dict(fila._mapping) if fila else None


async def crear_o_actualizar_autorizacion(
    sesion: AsyncSession,
    usuario_id: UUID,
    alias: str,
    version_politica: str,
    finalidad: str,
) -> dict[str, Any]:
    """Crea o actualiza el perfil y asienta el consentimiento en autorizacion_datos."""
    sql_perfil = text("""
        INSERT INTO perfil (id, alias, rol, estado, reputacion)
        VALUES (:id, :alias, 'reportante', 'activa', 0.500)
        ON CONFLICT (id) DO UPDATE SET
            alias = :alias,
            estado = 'activa',
            actualizado_en = now()
        RETURNING id, alias, rol::text, estado::text, reputacion, creado_en;
    """)
    fila_p = (await sesion.execute(sql_perfil, {"id": usuario_id, "alias": alias})).fetchone()
    perfil_dict = dict(fila_p._mapping)  # type: ignore[union-attr]

    sql_aut = text("""
        INSERT INTO autorizacion_datos (usuario_id, version_politica, finalidad)
        VALUES (:uid, :version, :finalidad)
        RETURNING id, version_politica, aceptada_en;
    """)
    fila_a = (
        await sesion.execute(
            sql_aut,
            {"uid": usuario_id, "version": version_politica, "finalidad": finalidad},
        )
    ).fetchone()
    aut_dict = dict(fila_a._mapping)  # type: ignore[union-attr]

    return {**perfil_dict, "autorizacion": aut_dict}


async def obtener_perfil_con_autorizacion(
    sesion: AsyncSession,
    usuario_id: UUID,
) -> dict[str, Any] | None:
    """Obtiene la ficha del perfil junto con su autorizacion de datos vigente."""
    sql_p = text("""
        SELECT id, alias, rol::text, estado::text, reputacion,
               reportes_corroborados, reportes_malos_confirmados, creado_en
        FROM perfil WHERE id = :id;
    """)
    fila_p = (await sesion.execute(sql_p, {"id": usuario_id})).fetchone()
    if not fila_p:
        return None

    perfil = dict(fila_p._mapping)
    aut = await obtener_autorizacion_vigente(sesion, usuario_id)
    perfil["autorizacion_vigente"] = aut
    return perfil


async def actualizar_alias_bd(
    sesion: AsyncSession,
    usuario_id: UUID,
    nuevo_alias: str,
) -> dict[str, Any]:
    """Actualiza el alias de un perfil existente."""
    sql = text("""
        UPDATE perfil
        SET alias = :alias, actualizado_en = now()
        WHERE id = :id
        RETURNING id, alias, rol::text, estado::text, reputacion,
                  reportes_corroborados, reportes_malos_confirmados, creado_en;
    """)
    fila = (await sesion.execute(sql, {"id": usuario_id, "alias": nuevo_alias})).fetchone()
    return dict(fila._mapping)  # type: ignore[union-attr]


_TEXTO_TELEFONO_ANONIMIZADO = "anonimizado"
_TEXTO_MENSAJE_ANONIMIZADO = "Dato anonimizado por supresion de cuenta (Ley 1581)."


async def anonimizar_y_dar_de_baja_cuenta(
    sesion: AsyncSession,
    usuario_id: UUID,
) -> tuple[dict[str, Any], list[str], dict[str, int]]:
    """Ejecuta en transaccion atomica la anonimizacion completa segun FR-007.

    Ademas de los reportes y la autorizacion, limpia los datos comerciales del
    titular: borra sus reclamos pendientes, anonimiza telefono y mensaje de los
    reclamos ya resueltos, desvincula sus establecimientos, y desactiva los
    precios oficiales y las promociones de esas tiendas. La operacion sigue
    siendo reversible solo por rollback: no se borra el perfil ni el historial.

    Devuelve el perfil anonimizado, las rutas de fotos a eliminar y un resumen
    con conteos sin PII para la auditoria.
    """
    sql_fotos = text("""
        SELECT foto_prueba_path FROM reporte_precio
        WHERE reportante_id = :id AND foto_prueba_path IS NOT NULL;
    """)
    filas_fotos = (await sesion.execute(sql_fotos, {"id": usuario_id})).fetchall()
    rutas_fotos = [str(f[0]) for f in filas_fotos if f[0]]

    # 1. Anonimizar reportes historicos
    sql_rep = text("""
        UPDATE reporte_precio
        SET reportante_id = NULL, foto_prueba_path = NULL
        WHERE reportante_id = :id;
    """)
    await sesion.execute(sql_rep, {"id": usuario_id})

    # 2. Anonimizar alias y cambiar estado a 'eliminada'
    alias_anonimo = f"eliminado_{str(usuario_id)[:8]}"
    sql_perfil = text("""
        UPDATE perfil
        SET alias = :alias, estado = 'eliminada', actualizado_en = now()
        WHERE id = :id
        RETURNING id, alias, estado::text;
    """)
    fila_perfil = (
        await sesion.execute(sql_perfil, {"id": usuario_id, "alias": alias_anonimo})
    ).fetchone()
    perfil_anon = dict(fila_perfil._mapping)  # type: ignore[union-attr]

    # 3. Revocar autorizacion de datos
    sql_aut = text("""
        UPDATE autorizacion_datos
        SET revocada_en = now()
        WHERE usuario_id = :id AND revocada_en IS NULL;
    """)
    await sesion.execute(sql_aut, {"id": usuario_id})

    # 4. Borrar reclamos pendientes: un titular eliminado no puede quedar en la
    #    cola de moderacion con telefono y mensaje.
    sql_borrar_reclamos = text("""
        DELETE FROM solicitud_verificacion_comercio
        WHERE usuario_id = :id AND estado = 'pendiente'
        RETURNING id;
    """)
    reclamos_borrados = len(
        (await sesion.execute(sql_borrar_reclamos, {"id": usuario_id})).fetchall()
    )

    # 5. Anonimizar telefono y mensaje de los reclamos ya resueltos. La fila se
    #    conserva porque es historial de moderacion; la PII no.
    sql_anonimizar_reclamos = text("""
        UPDATE solicitud_verificacion_comercio
        SET telefono_contacto = :telefono, mensaje = :mensaje
        WHERE usuario_id = :id
        RETURNING id;
    """)
    reclamos_anonimizados = len(
        (
            await sesion.execute(
                sql_anonimizar_reclamos,
                {
                    "id": usuario_id,
                    "telefono": _TEXTO_TELEFONO_ANONIMIZADO,
                    "mensaje": _TEXTO_MENSAJE_ANONIMIZADO,
                },
            )
        ).fetchall()
    )

    # 6. Desvincular las tiendas del titular. La tienda sigue existiendo, pero
    #    queda sin dueno y sin verificar hasta que otro comercio la reclame.
    sql_desvincular = text("""
        UPDATE establecimiento
        SET comercio_id = NULL,
            estado_verificacion = 'sin_dueno',
            actualizado_en = now()
        WHERE comercio_id = :id
        RETURNING id;
    """)
    establecimientos = [
        fila.id for fila in (await sesion.execute(sql_desvincular, {"id": usuario_id})).fetchall()
    ]

    precios_desactivados = 0
    promociones_revocadas = 0
    if establecimientos:
        # 7. Desactivar los precios oficiales de esas tiendas. Se conserva la
        #    fila historica para no perder trazabilidad de lo ya publicado.
        sql_precios = text("""
            UPDATE precio_oficial
            SET activo = false
            WHERE establecimiento_id = ANY(:establecimientos) AND activo = true
            RETURNING presentacion_id;
        """)
        precios_desactivados = len(
            (await sesion.execute(sql_precios, {"establecimientos": establecimientos})).fetchall()
        )

        # 8. Revocar las promociones activas de esas tiendas, conservando el
        #    registro y su fecha de revocacion.
        sql_promociones = text("""
            UPDATE promocion
            SET activa = false, revocada_en = now()
            WHERE establecimiento_id = ANY(:establecimientos) AND activa = true
            RETURNING id;
        """)
        promociones_revocadas = len(
            (
                await sesion.execute(sql_promociones, {"establecimientos": establecimientos})
            ).fetchall()
        )

    resumen_comercial = {
        "reclamos_pendientes_borrados": reclamos_borrados,
        "reclamos_anonimizados": reclamos_anonimizados,
        "establecimientos_desvinculados": len(establecimientos),
        "precios_oficiales_desactivados": precios_desactivados,
        "promociones_revocadas": promociones_revocadas,
    }
    return perfil_anon, rutas_fotos, resumen_comercial
