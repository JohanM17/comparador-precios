"""Repositorio de base de datos para perfiles, autorizaciones Ley 1581 y anonimizacion."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.bloqueos import bloquear_por_usuario
from app.compartido.errores import ConflictoError


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
        WHERE perfil.estado <> 'eliminada'
        RETURNING id, alias, rol::text, estado::text, reputacion, creado_en;
    """)
    fila_p = (await sesion.execute(sql_perfil, {"id": usuario_id, "alias": alias})).fetchone()
    if fila_p is None:
        # El upsert no encontro fila porque el perfil esta eliminado. No se
        # escribe la autorizacion ni se reactiva la cuenta.
        raise ConflictoError("La cuenta fue eliminada y no puede reactivarse.")
    perfil_dict = dict(fila_p._mapping)

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
) -> dict[str, Any] | None:
    """Actualiza el alias solo si la cuenta sigue activa; None si esta eliminada."""
    sql = text("""
        UPDATE perfil
        SET alias = :alias, actualizado_en = now()
        WHERE id = :id AND estado = 'activa'
        RETURNING id, alias, rol::text, estado::text, reputacion,
                  reportes_corroborados, reportes_malos_confirmados, creado_en;
    """)
    fila = (await sesion.execute(sql, {"id": usuario_id, "alias": nuevo_alias})).fetchone()
    return dict(fila._mapping) if fila is not None else None


_TEXTO_TELEFONO_ANONIMIZADO = "anonimizado"
_TEXTO_MENSAJE_ANONIMIZADO = "Dato anonimizado por supresion de cuenta (Ley 1581)."


async def anonimizar_y_dar_de_baja_cuenta(
    sesion: AsyncSession,
    usuario_id: UUID,
) -> tuple[dict[str, Any], list[str], dict[str, int], list[UUID]]:
    """Ejecuta en transaccion atomica la anonimizacion completa segun FR-007.

    El orden de bloqueos sigue el de la aprobacion de reclamos
    (`solicitud -> establecimiento -> perfil`) para no formar un ciclo: por eso
    el perfil se actualiza al final, despues de reclamos, tiendas, precios y
    promociones.

    La proyeccion `precio_vigente` de las tiendas desvinculadas se elimina; de
    lo contrario el comparador seguiria mostrando `sello='oficial'` y el precio
    del comercio hasta el siguiente recalculo. Se devuelven los `producto_id`
    afectados para invalidar la cache.

    Devuelve el perfil anonimizado, las rutas de fotos a eliminar, un resumen
    con conteos sin PII para la auditoria y los productos a invalidar.
    """
    # Misma clave que usa el reclamo de titularidad: serializa ambos flujos
    # antes de tocar solicitudes, establecimientos o el perfil.
    await bloquear_por_usuario(sesion, usuario_id)

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

    # 2. Borrar reclamos pendientes: un titular eliminado no puede quedar en la
    #    cola de moderacion con telefono y mensaje.
    sql_borrar_reclamos = text("""
        DELETE FROM solicitud_verificacion_comercio
        WHERE usuario_id = :id AND estado = 'pendiente'
        RETURNING id;
    """)
    reclamos_borrados = len(
        (await sesion.execute(sql_borrar_reclamos, {"id": usuario_id})).fetchall()
    )

    # 3. Anonimizar telefono y mensaje de los reclamos ya resueltos. La fila se
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

    # 4. Borrar el texto de las apelaciones de sanciones. La sancion se
    #    conserva como historial de moderacion, pero su relato puede tener PII.
    sql_apelaciones = text("""
        UPDATE sancion
        SET apelacion = NULL
        WHERE usuario_id = :id AND apelacion IS NOT NULL
        RETURNING id;
    """)
    apelaciones_anonimizadas = len(
        (await sesion.execute(sql_apelaciones, {"id": usuario_id})).fetchall()
    )

    # 5. Desvincular las tiendas del titular. La tienda sigue existiendo, pero
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
    precios_vigentes_eliminados = 0
    productos_afectados: set[UUID] = set()
    if establecimientos:
        # 6. Desactivar los precios oficiales de esas tiendas. Se conserva la
        #    fila historica para no perder trazabilidad de lo ya publicado.
        sql_precios = text("""
            UPDATE precio_oficial
            SET activo = false
            WHERE establecimiento_id = ANY(:establecimientos) AND activo = true
            RETURNING producto_id;
        """)
        filas_precios = (
            await sesion.execute(sql_precios, {"establecimientos": establecimientos})
        ).fetchall()
        precios_desactivados = len(filas_precios)
        productos_afectados.update(fila.producto_id for fila in filas_precios)

        # 7. Revocar las promociones activas de esas tiendas, conservando el
        #    registro y su fecha de revocacion.
        sql_promociones = text("""
            UPDATE promocion
            SET activa = false, revocada_en = now()
            WHERE establecimiento_id = ANY(:establecimientos) AND activa = true
            RETURNING producto_id;
        """)
        filas_promociones = (
            await sesion.execute(sql_promociones, {"establecimientos": establecimientos})
        ).fetchall()
        promociones_revocadas = len(filas_promociones)
        productos_afectados.update(fila.producto_id for fila in filas_promociones)

        # 8. Eliminar la proyeccion vigente. Si solo se desactivara el oficial,
        #    el comparador seguiria sirviendo `sello='oficial'` desde esta tabla
        #    hasta que el job de reconstruccion lo corrija.
        sql_precio_vigente = text("""
            DELETE FROM precio_vigente
            WHERE establecimiento_id = ANY(:establecimientos)
            RETURNING producto_id;
        """)
        filas_vigentes = (
            await sesion.execute(sql_precio_vigente, {"establecimientos": establecimientos})
        ).fetchall()
        precios_vigentes_eliminados = len(filas_vigentes)
        productos_afectados.update(fila.producto_id for fila in filas_vigentes)

    # 9. Anonimizar el perfil al final, cuando ya se liberaron los bloqueos
    #    comerciales. Un moderador o admin eliminado pierde ademas su rol.
    alias_anonimo = f"eliminado_{str(usuario_id)[:8]}"
    sql_perfil = text("""
        UPDATE perfil
        SET alias = :alias,
            estado = 'eliminada',
            rol = 'reportante',
            actualizado_en = now()
        WHERE id = :id
        RETURNING id, alias, estado::text, rol::text;
    """)
    fila_perfil = (
        await sesion.execute(sql_perfil, {"id": usuario_id, "alias": alias_anonimo})
    ).fetchone()
    perfil_anon = dict(fila_perfil._mapping)  # type: ignore[union-attr]

    # 10. Revocar autorizacion de datos
    sql_aut = text("""
        UPDATE autorizacion_datos
        SET revocada_en = now()
        WHERE usuario_id = :id AND revocada_en IS NULL;
    """)
    await sesion.execute(sql_aut, {"id": usuario_id})

    resumen_comercial = {
        "reclamos_pendientes_borrados": reclamos_borrados,
        "reclamos_anonimizados": reclamos_anonimizados,
        "establecimientos_desvinculados": len(establecimientos),
        "precios_oficiales_desactivados": precios_desactivados,
        "promociones_revocadas": promociones_revocadas,
        "precios_vigentes_eliminados": precios_vigentes_eliminados,
        "apelaciones_anonimizadas": apelaciones_anonimizadas,
    }
    return perfil_anon, rutas_fotos, resumen_comercial, sorted(productos_afectados)
