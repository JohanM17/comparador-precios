"""Consultas de base de datos del modulo comercial (Etapa 2)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def obtener_establecimiento(
    sesion: AsyncSession,
    establecimiento_id: UUID,
) -> dict[str, Any] | None:
    """Datos de titularidad y verificacion de un establecimiento."""
    sql = text("""
        SELECT id, nombre, tipo::text AS tipo, barrio, direccion,
               comercio_id, estado_verificacion::text AS estado_verificacion, activo
        FROM public.establecimiento
        WHERE id = :id;
    """)
    fila = (await sesion.execute(sql, {"id": establecimiento_id})).first()
    return dict(fila._mapping) if fila else None


async def existe_reclamo_abierto(sesion: AsyncSession, establecimiento_id: UUID) -> bool:
    """Indica si el establecimiento ya tiene un reclamo de titularidad sin resolver."""
    sql = text("""
        SELECT 1 FROM public.solicitud_verificacion_comercio
        WHERE establecimiento_id = :est_id AND estado = 'pendiente'
        LIMIT 1;
    """)
    return (await sesion.execute(sql, {"est_id": establecimiento_id})).first() is not None


async def crear_reclamo(
    sesion: AsyncSession,
    usuario_id: UUID,
    establecimiento_id: UUID,
    telefono_contacto: str,
    mensaje: str,
) -> dict[str, Any]:
    """Registra el reclamo de titularidad y devuelve su acuse."""
    sql = text("""
        INSERT INTO public.solicitud_verificacion_comercio
            (usuario_id, establecimiento_id, telefono_contacto, mensaje)
        VALUES (:usuario_id, :est_id, :telefono, :mensaje)
        RETURNING id, establecimiento_id, estado::text AS estado, creado_en;
    """)
    fila = (
        await sesion.execute(
            sql,
            {
                "usuario_id": usuario_id,
                "est_id": establecimiento_id,
                "telefono": telefono_contacto,
                "mensaje": mensaje,
            },
        )
    ).first()
    if fila is None:  # pragma: no cover
        raise RuntimeError("El reclamo no devolvio fila")
    return dict(fila._mapping)


async def listar_solicitudes_pendientes(
    sesion: AsyncSession,
    limite: int,
) -> list[dict[str, Any]]:
    """Reclamos de titularidad sin resolver, del mas antiguo al mas reciente.

    El telefono de contacto viaja porque es el unico dato con el que un
    moderador puede verificar que quien reclama responde por el local. La ruta
    que la usa exige rol de moderador.
    """
    sql = text("""
        SELECT s.id, s.establecimiento_id, s.telefono_contacto, s.mensaje,
               s.estado::text AS estado, s.creado_en,
               e.nombre AS establecimiento_nombre,
               e.barrio AS establecimiento_barrio,
               e.direccion AS establecimiento_direccion,
               p.alias AS solicitante_alias
        FROM public.solicitud_verificacion_comercio s
        JOIN public.establecimiento e ON e.id = s.establecimiento_id
        JOIN public.perfil p ON p.id = s.usuario_id
        WHERE s.estado = 'pendiente'
        ORDER BY s.creado_en ASC
        LIMIT :limite;
    """)
    filas = (await sesion.execute(sql, {"limite": limite})).fetchall()
    return [dict(f._mapping) for f in filas]


async def obtener_solicitud(sesion: AsyncSession, solicitud_id: UUID) -> dict[str, Any] | None:
    """Solicitud de verificacion con el usuario y el establecimiento implicados."""
    sql = text("""
        SELECT id, usuario_id, establecimiento_id, estado::text AS estado, creado_en
        FROM public.solicitud_verificacion_comercio
        WHERE id = :id;
    """)
    fila = (await sesion.execute(sql, {"id": solicitud_id})).first()
    return dict(fila._mapping) if fila else None


async def resolver_solicitud(
    sesion: AsyncSession,
    solicitud_id: UUID,
    moderador_id: UUID,
    aprobada: bool,
) -> None:
    """Marca la solicitud como verificada o la devuelve a sin dueno."""
    sql = text("""
        UPDATE public.solicitud_verificacion_comercio
        SET estado = CAST(:estado AS estado_verificacion),
            verificado_por = :moderador_id,
            verificado_en = now()
        WHERE id = :id;
    """)
    await sesion.execute(
        sql,
        {
            "id": solicitud_id,
            "moderador_id": moderador_id,
            "estado": "verificado" if aprobada else "sin_dueno",
        },
    )


async def enlazar_comercio(
    sesion: AsyncSession,
    establecimiento_id: UUID,
    comercio_id: UUID,
) -> None:
    """Asigna el dueno del establecimiento y lo marca como verificado."""
    sql = text("""
        UPDATE public.establecimiento
        SET comercio_id = :comercio_id,
            estado_verificacion = 'verificado'
        WHERE id = :est_id;
    """)
    await sesion.execute(sql, {"est_id": establecimiento_id, "comercio_id": comercio_id})


async def asignar_rol_comercio(sesion: AsyncSession, usuario_id: UUID) -> None:
    """Eleva el rol del usuario a comercio sin tocar a quien ya es moderador."""
    sql = text("""
        UPDATE public.perfil
        SET rol = 'comercio'
        WHERE id = :id AND rol = 'reportante';
    """)
    await sesion.execute(sql, {"id": usuario_id})


async def listar_establecimientos_de_comercio(
    sesion: AsyncSession,
    comercio_id: UUID,
    revalidar_dias: int,
) -> list[dict[str, Any]]:
    """Establecimientos verificados del comercio, con el estado de sus precios oficiales."""
    sql = text("""
        SELECT e.id, e.nombre, e.tipo::text AS tipo, e.barrio, e.direccion,
               e.estado_verificacion::text AS estado_verificacion,
               COALESCE(conteo.n_precios, 0) AS n_precios_oficiales,
               COALESCE(conteo.n_viejos, 0) AS n_por_revalidar
        FROM public.establecimiento e
        LEFT JOIN (
            SELECT establecimiento_id,
                   COUNT(*) AS n_precios,
                   COUNT(*) FILTER (
                       WHERE revalidado_en < now() - make_interval(days => :dias)
                   ) AS n_viejos
            FROM public.precio_oficial
            WHERE activo = true
            GROUP BY establecimiento_id
        ) conteo ON conteo.establecimiento_id = e.id
        WHERE e.comercio_id = :comercio_id AND e.activo = true
        ORDER BY e.nombre;
    """)
    filas = (
        await sesion.execute(sql, {"comercio_id": comercio_id, "dias": revalidar_dias})
    ).fetchall()
    return [dict(f._mapping) for f in filas]


async def obtener_presentaciones(
    sesion: AsyncSession,
    presentacion_ids: list[UUID],
) -> dict[UUID, dict[str, Any]]:
    """Presentaciones activas indexadas por identificador, con su producto y cantidad base."""
    if not presentacion_ids:
        return {}
    sql = text("""
        SELECT pr.id, pr.producto_id, pr.cantidad_base, pr.activa
        FROM public.presentacion pr
        JOIN public.producto p ON p.id = pr.producto_id
        WHERE pr.id = ANY(:ids) AND pr.activa = true AND p.activo = true;
    """)
    filas = (await sesion.execute(sql, {"ids": presentacion_ids})).fetchall()
    return {f.id: dict(f._mapping) for f in filas}


async def upsert_precio_oficial(
    sesion: AsyncSession,
    presentacion_id: UUID,
    establecimiento_id: UUID,
    producto_id: UUID,
    comercio_id: UUID,
    precio_cop: int,
    precio_por_base: Decimal,
) -> None:
    """Publica o actualiza el precio oficial de una presentacion en un establecimiento."""
    sql = text("""
        INSERT INTO public.precio_oficial (
            presentacion_id, establecimiento_id, producto_id, comercio_id,
            precio_cop, precio_por_base, actualizado_en, revalidado_en, activo
        ) VALUES (
            :pres_id, :est_id, :prod_id, :comercio_id,
            :precio_cop, :precio_por_base, now(), now(), true
        )
        ON CONFLICT (presentacion_id, establecimiento_id) DO UPDATE SET
            producto_id = EXCLUDED.producto_id,
            comercio_id = EXCLUDED.comercio_id,
            precio_cop = EXCLUDED.precio_cop,
            precio_por_base = EXCLUDED.precio_por_base,
            actualizado_en = now(),
            revalidado_en = now(),
            activo = true;
    """)
    await sesion.execute(
        sql,
        {
            "pres_id": presentacion_id,
            "est_id": establecimiento_id,
            "prod_id": producto_id,
            "comercio_id": comercio_id,
            "precio_cop": precio_cop,
            "precio_por_base": precio_por_base,
        },
    )


async def revalidar_precios(
    sesion: AsyncSession,
    establecimiento_id: UUID,
    comercio_id: UUID,
) -> tuple[int, datetime | None]:
    """Renueva la fecha de confirmacion de los precios oficiales sin cambiar sus valores."""
    sql = text("""
        UPDATE public.precio_oficial
        SET revalidado_en = now()
        WHERE establecimiento_id = :est_id AND comercio_id = :comercio_id AND activo = true
        RETURNING presentacion_id, revalidado_en;
    """)
    filas = (
        await sesion.execute(sql, {"est_id": establecimiento_id, "comercio_id": comercio_id})
    ).fetchall()
    momento = filas[0].revalidado_en if filas else None
    return len(filas), momento


async def listar_presentaciones_con_precio_oficial(
    sesion: AsyncSession,
    establecimiento_id: UUID,
) -> list[UUID]:
    """Presentaciones del establecimiento que tienen precio oficial activo."""
    sql = text("""
        SELECT presentacion_id FROM public.precio_oficial
        WHERE establecimiento_id = :est_id AND activo = true;
    """)
    filas = (await sesion.execute(sql, {"est_id": establecimiento_id})).fetchall()
    return [f.presentacion_id for f in filas]


async def insertar_promocion(
    sesion: AsyncSession,
    datos: dict[str, Any],
) -> dict[str, Any]:
    """Publica una promocion comercial ya validada contra la Ley 1480."""
    sql = text("""
        INSERT INTO public.promocion (
            establecimiento_id, producto_id, presentacion_id, comercio_id,
            titulo, tipo, porcentaje_descuento, precio_especial_cop, pague_x, lleve_y,
            condiciones, vigente_desde, vigente_hasta, hasta_revocar
        ) VALUES (
            :est_id, :prod_id, :pres_id, :comercio_id,
            :titulo, CAST(:tipo AS tipo_promocion), :porcentaje, :precio_especial,
            :pague_x, :lleve_y,
            :condiciones, :vigente_desde, :vigente_hasta, :hasta_revocar
        )
        RETURNING id, establecimiento_id, producto_id, presentacion_id, titulo,
                  tipo::text AS tipo, porcentaje_descuento, precio_especial_cop,
                  pague_x, lleve_y, condiciones, vigente_desde, vigente_hasta,
                  hasta_revocar, activa;
    """)
    fila = (await sesion.execute(sql, datos)).first()
    if fila is None:  # pragma: no cover
        raise RuntimeError("La promocion no devolvio fila")
    return dict(fila._mapping)


async def listar_promociones_de_establecimiento(
    sesion: AsyncSession,
    establecimiento_id: UUID,
    solo_activas: bool = True,
) -> list[dict[str, Any]]:
    """Promociones publicadas por el comercio en uno de sus establecimientos."""
    sql = text("""
        SELECT id, establecimiento_id, producto_id, presentacion_id, titulo,
               tipo::text AS tipo, porcentaje_descuento, precio_especial_cop,
               pague_x, lleve_y, condiciones, vigente_desde, vigente_hasta,
               hasta_revocar, activa
        FROM public.promocion
        WHERE establecimiento_id = :est_id
          AND (:solo_activas = false OR activa = true)
        ORDER BY vigente_desde DESC;
    """)
    filas = (
        await sesion.execute(sql, {"est_id": establecimiento_id, "solo_activas": solo_activas})
    ).fetchall()
    return [dict(f._mapping) for f in filas]


async def revocar_promocion(
    sesion: AsyncSession,
    promocion_id: UUID,
    comercio_id: UUID,
) -> UUID | None:
    """Revoca una promocion propia y devuelve su producto, o None si no existia."""
    sql = text("""
        UPDATE public.promocion
        SET activa = false, revocada_en = now()
        WHERE id = :id AND comercio_id = :comercio_id AND activa = true
        RETURNING producto_id;
    """)
    fila = (await sesion.execute(sql, {"id": promocion_id, "comercio_id": comercio_id})).first()
    producto_id: UUID | None = fila.producto_id if fila is not None else None
    return producto_id
