"""Repositorio de base de datos para sugerencias de presentacion y casos de moderacion."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def verificar_autorizacion_vigente(sesion: AsyncSession, usuario_id: UUID) -> bool:
    """Valida si el usuario cuenta con consentimiento de datos Ley 1581 activo."""
    sql = text("""
        SELECT 1 FROM autorizacion_datos
        WHERE usuario_id = :usuario_id AND revocada_en IS NULL;
    """)
    fila = (await sesion.execute(sql, {"usuario_id": usuario_id})).fetchone()
    return fila is not None


async def crear_sugerencia_presentacion_bd(
    sesion: AsyncSession,
    usuario_id: UUID,
    producto_id: UUID,
    texto_libre: str,
    marca: str | None,
    valor_cantidad: Decimal | None,
    unidad: str | None,
    codigo_barras: str | None,
) -> tuple[UUID, UUID]:
    """Crea una sugerencia de presentacion y abre un caso de moderacion."""
    sql_sug = text("""
        INSERT INTO sugerencia_presentacion (
            usuario_id, producto_id, texto_libre, marca,
            valor_cantidad, unidad, codigo_barras, estado
        ) VALUES (
            :usuario_id, :producto_id, :texto_libre, :marca, :valor_cantidad,
            CAST(:unidad AS unidad_entrada), :codigo_barras, 'pendiente'
        )
        RETURNING id;
    """)
    sug_id = await sesion.scalar(
        sql_sug,
        {
            "usuario_id": usuario_id,
            "producto_id": producto_id,
            "texto_libre": texto_libre,
            "marca": marca,
            "valor_cantidad": valor_cantidad,
            "unidad": unidad,
            "codigo_barras": codigo_barras,
        },
    )
    sugerencia_uuid = UUID(str(sug_id))

    detalle_json = json.dumps(
        {
            "producto_id": str(producto_id),
            "texto_libre": texto_libre,
            "marca": marca,
            "valor_cantidad": str(valor_cantidad) if valor_cantidad else None,
            "unidad": unidad,
            "codigo_barras": codigo_barras,
        }
    )
    sql_caso = text("""
        INSERT INTO caso_moderacion (
            tipo, referencia_tabla, referencia_id, detalle, prioridad, estado
        ) VALUES (
            'sugerencia_presentacion', 'sugerencia_presentacion', :ref_id,
            CAST(:detalle AS jsonb), 3, 'abierto'
        )
        RETURNING id;
    """)
    caso_id = await sesion.scalar(sql_caso, {"ref_id": sugerencia_uuid, "detalle": detalle_json})
    return sugerencia_uuid, UUID(str(caso_id))


async def obtener_sugerencia_por_id(
    sesion: AsyncSession, sugerencia_id: UUID
) -> dict[str, Any] | None:
    """Obtiene una sugerencia de presentacion por id."""
    sql = text("""
        SELECT id, usuario_id, producto_id, texto_libre, marca, valor_cantidad,
               unidad::text, codigo_barras, estado, creado_en
        FROM sugerencia_presentacion WHERE id = :id;
    """)
    fila = (await sesion.execute(sql, {"id": sugerencia_id})).fetchone()
    return dict(fila._mapping) if fila else None


async def resolver_sugerencia_bd(
    sesion: AsyncSession,
    sugerencia_id: UUID,
    nuevo_estado: str,
    moderador_id: UUID,
    decision: str,
    nota: str | None = None,
) -> None:
    """Actualiza el estado de la sugerencia y resuelve el caso de moderacion correspondiente."""
    await sesion.execute(
        text("UPDATE sugerencia_presentacion SET estado = :estado WHERE id = :id;"),
        {"id": sugerencia_id, "estado": nuevo_estado},
    )
    sql_caso = text("""
        UPDATE caso_moderacion
        SET estado = 'resuelto', decision = CAST(:decision AS decision_caso),
            moderador_id = :moderador_id, nota = :nota, resuelto_en = now()
        WHERE referencia_tabla = 'sugerencia_presentacion' AND referencia_id = :id;
    """)
    await sesion.execute(
        sql_caso,
        {"id": sugerencia_id, "decision": decision, "moderador_id": moderador_id, "nota": nota},
    )
