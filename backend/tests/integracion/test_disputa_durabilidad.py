"""Integracion de la durabilidad de una disputa D-01 en base aislada.

Se ejecuta con `scripts/integracion_aislada.py`; no apunta a la base compartida.
Cubre el corte durable que deja `confirmar` y la validacion de la version del
precio oficial cuando el comercio lo cambia durante el caso.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.compartido.errores import ConflictoError
from app.compartido.seguridad import UsuarioAutenticado
from app.config import obtener_configuracion
from app.modulos.moderacion.esquemas_casos import ResolverCasoEntrada
from app.modulos.moderacion.servicio_casos import ServicioCasosModeracion
from app.puertos.politica_precio import OficialConContraste


def _hay_url_bd() -> bool:
    configuracion = obtener_configuracion()
    return bool(configuracion.DATABASE_URL or configuracion.MIGRATIONS_DATABASE_URL)


pytestmark = pytest.mark.skipif(
    not _hay_url_bd(),
    reason="Sin base de datos: usa scripts/integracion_aislada.py para esta prueba.",
)


class CacheNula:
    """Cache en memoria sin efectos externos para la prueba de integracion."""

    def __init__(self) -> None:
        self.invalidados: list[UUID] = []

    async def invalidar_producto(self, producto_id: UUID) -> None:
        self.invalidados.append(producto_id)

    async def limpiar(self) -> None:
        return None


async def _crear_contexto() -> dict[str, Any]:
    """Crea catalogo, establecimiento, perfiles y precio oficial unicos por prueba."""
    sufijo = uuid4().hex[:10]
    ahora = datetime.now(UTC)
    async with sesion_transaccional() as sesion:
        producto_id = (
            await sesion.execute(
                text("""
                    INSERT INTO public.producto
                        (nombre, nombre_norm, categoria_id, unidad_base)
                    VALUES (:nombre, :nombre_norm, 1, 'g')
                    RETURNING id;
                """),
                {"nombre": f"Disputa {sufijo}", "nombre_norm": f"disputa_{sufijo}"},
            )
        ).scalar_one()
        presentacion_id = (
            await sesion.execute(
                text("""
                    INSERT INTO public.presentacion
                        (producto_id, marca, valor_cantidad, unidad, multiplicador,
                         cantidad_base, etiqueta, etiqueta_norm)
                    VALUES (:prod, :marca, 1000, 'g', 1, 1000, :etiqueta, :etiqueta_norm)
                    RETURNING id;
                """),
                {
                    "prod": producto_id,
                    "marca": f"Marca {sufijo}",
                    "etiqueta": f"Paquete {sufijo} 1 kg",
                    "etiqueta_norm": f"paquete_{sufijo}_1_kg",
                },
            )
        ).scalar_one()
        establecimiento_id = (
            await sesion.execute(
                text("""
                    INSERT INTO public.establecimiento
                        (nombre, tipo, direccion, ubicacion)
                    VALUES (
                        :nombre, 'tienda_barrio', :direccion,
                        ST_SetSRID(ST_MakePoint(-75.6811, 4.5339), 4326)::geography
                    )
                    RETURNING id;
                """),
                {
                    "nombre": f"Tienda disputa {sufijo}",
                    "direccion": f"Calle disputa {sufijo}",
                },
            )
        ).scalar_one()

        async def crear_perfil(rol: str) -> UUID:
            perfil_id = uuid4()
            await sesion.execute(
                text("""
                    INSERT INTO public.perfil (id, alias, rol, estado, reputacion)
                    VALUES (
                        :id, :alias, CAST(:rol AS rol_usuario), 'activa', 0.700
                    );
                """),
                {"id": perfil_id, "alias": f"u_{perfil_id.hex[:8]}", "rol": rol},
            )
            return perfil_id

        comercio_id = await crear_perfil("comercio")
        moderador_id = await crear_perfil("moderador")
        reportantes = [await crear_perfil("reportante") for _ in range(6)]

        await sesion.execute(
            text("""
                INSERT INTO public.precio_oficial (
                    presentacion_id, establecimiento_id, producto_id, comercio_id,
                    precio_cop, precio_por_base
                ) VALUES (
                    :pres, :est, :prod, :comercio, 3050, 3.050000
                );
            """),
            {
                "pres": presentacion_id,
                "est": establecimiento_id,
                "prod": producto_id,
                "comercio": comercio_id,
            },
        )

        reporte_ids = []
        for indice, reportante in enumerate(reportantes[:3]):
            reporte_ids.append(
                (
                    await sesion.execute(
                        text("""
                            INSERT INTO public.reporte_precio (
                                presentacion_id, establecimiento_id, producto_id,
                                precio_cop, cantidad_base_snapshot, precio_por_base,
                                fuente, reportante_id, observado_en, estado,
                                estado_original, conjunto_referencia
                            ) VALUES (
                                :pres, :est, :prod, :precio, 1000, :precio_base,
                                'usuario', :uid, :observado, 'aceptado',
                                'aceptado', 'sin_referencia'
                            )
                            RETURNING id;
                        """),
                        {
                            "pres": presentacion_id,
                            "est": establecimiento_id,
                            "prod": producto_id,
                            "precio": 2600 if indice < 2 else 2650,
                            "precio_base": Decimal("2.600000")
                            if indice < 2
                            else Decimal("2.650000"),
                            "uid": reportante,
                            "observado": ahora - timedelta(hours=5 + indice * 5),
                        },
                    )
                ).scalar_one()
            )

    return {
        "producto_id": producto_id,
        "presentacion_id": presentacion_id,
        "establecimiento_id": establecimiento_id,
        "moderador_id": moderador_id,
        "reportantes": reportantes,
        "reporte_ids": reporte_ids,
        "ahora": ahora,
    }


async def _caso_abierto(presentacion_id: UUID, establecimiento_id: UUID) -> dict[str, Any] | None:
    async with sesion_transaccional() as sesion:
        fila = (
            await sesion.execute(
                text("""
                    SELECT id, estado::text, detalle
                    FROM public.caso_moderacion
                    WHERE tipo = 'disputa_precio'
                      AND referencia_tabla = 'presentacion'
                      AND referencia_id = :pres
                      AND estado IN ('abierto', 'en_revision')
                      AND detalle ->> 'establecimiento_id' = :est
                    ORDER BY creado_en DESC
                    LIMIT 1;
                """),
                {"pres": presentacion_id, "est": str(establecimiento_id)},
            )
        ).first()
        return dict(fila._mapping) if fila else None


async def _resolver(
    caso_id: UUID,
    decision: str,
    moderador_id: UUID,
    cache: CacheNula,
) -> Any:
    moderador = UsuarioAutenticado(
        id=moderador_id, email="mod@armenia.gov.co", rol="moderador", estado="activa"
    )
    entrada = ResolverCasoEntrada(decision=decision, nota="Decision de prueba integracion")  # type: ignore[arg-type]
    async with sesion_transaccional() as sesion:
        servicio = ServicioCasosModeracion(
            sesion=sesion,
            cache=cache,  # type: ignore[arg-type]
            politica=OficialConContraste(),
        )
        return await servicio.resolver_caso(caso_id, entrada, moderador)


@pytest.mark.asyncio
async def test_confirmar_es_durable_y_solo_reportes_posteriores_reabren() -> None:
    """El corte de `confirmar` sobrevive al recalculo con los mismos reportes."""
    ctx = await _crear_contexto()
    pres = ctx["presentacion_id"]
    est = ctx["establecimiento_id"]
    ahora = ctx["ahora"]

    async with sesion_transaccional() as sesion:
        resultado = await OficialConContraste().recalcular_par(sesion, pres, est, ahora)
    assert resultado is not None and resultado.sello == "en_disputa"

    caso = await _caso_abierto(pres, est)
    assert caso is not None
    caso_id = caso["id"]

    await _resolver(caso_id, "confirmar", ctx["moderador_id"], CacheNula())

    async with sesion_transaccional() as sesion:
        vigente = (
            await sesion.execute(
                text("""
                    SELECT precio_cop, sello::text, motivo_sello,
                           n_reportes_validos, n_fuentes, precio_oficial_cop,
                           diferencia_pct, requiere_revalidacion,
                           ultimo_reporte_en, reporte_origen_id
                    FROM public.precio_vigente
                    WHERE presentacion_id = :pres AND establecimiento_id = :est;
                """),
                {"pres": pres, "est": est},
            )
        ).first()
        resuelto = (
            await sesion.execute(
                text("SELECT resuelto_en FROM public.caso_moderacion WHERE id = :id;"),
                {"id": caso_id},
            )
        ).scalar_one()
    assert vigente is not None
    assert vigente.precio_cop == 3050
    assert vigente.sello == "oficial"
    assert vigente.motivo_sello == "Precio oficial confirmado por moderacion"
    assert vigente.precio_oficial_cop == 3050
    assert vigente.diferencia_pct == 0
    assert vigente.requiere_revalidacion is False
    assert vigente.ultimo_reporte_en >= resuelto
    assert vigente.reporte_origen_id is None
    assert vigente.n_reportes_validos == 3
    assert vigente.n_fuentes == 3

    # Doble resolucion: el caso ya esta resuelto.
    with pytest.raises(ConflictoError):
        await _resolver(caso_id, "confirmar", ctx["moderador_id"], CacheNula())

    # Recalculo posterior con los mismos reportes: no revive la disputa.
    async with sesion_transaccional() as sesion:
        resultado = await OficialConContraste().recalcular_par(
            sesion, pres, est, resuelto + timedelta(minutes=5)
        )
    assert resultado is not None and resultado.sello == "oficial"
    assert await _caso_abierto(pres, est) is None

    # Reportes posteriores al corte: la comunidad puede volver a levantar la mano.
    nuevos_observados = [resuelto + timedelta(minutes=1 + i) for i in range(3)]
    async with sesion_transaccional() as sesion:
        for indice, observado in enumerate(nuevos_observados):
            await sesion.execute(
                text("""
                    INSERT INTO public.reporte_precio (
                        presentacion_id, establecimiento_id, producto_id,
                        precio_cop, cantidad_base_snapshot, precio_por_base,
                        fuente, reportante_id, observado_en, estado,
                        estado_original, conjunto_referencia
                    ) VALUES (
                        :pres, :est, :prod, 2600, 1000, 2.600000,
                        'usuario', :uid, :observado, 'aceptado',
                        'aceptado', 'sin_referencia'
                    );
                """),
                {
                    "pres": pres,
                    "est": est,
                    "prod": ctx["producto_id"],
                    "uid": ctx["reportantes"][3 + indice],
                    "observado": observado,
                },
            )

    async with sesion_transaccional() as sesion:
        resultado = await OficialConContraste().recalcular_par(
            sesion, pres, est, resuelto + timedelta(hours=1)
        )
    assert resultado is not None and resultado.sello == "en_disputa"
    nuevo_caso = await _caso_abierto(pres, est)
    assert nuevo_caso is not None and nuevo_caso["id"] != caso_id

    # Los reportes historicos siguen intactos: no se rechazaron ni se modificaron.
    async with sesion_transaccional() as sesion:
        intactos = (
            await sesion.execute(
                text("""
                    SELECT count(*) FROM public.reporte_precio
                    WHERE id = ANY(:ids) AND estado = 'aceptado';
                """),
                {"ids": ctx["reporte_ids"]},
            )
        ).scalar_one()
    assert intactos == 3


@pytest.mark.asyncio
async def test_precio_cambiado_refresca_el_caso_y_el_segundo_intento_resuelve() -> None:
    """El 409 deja el detalle actualizado para que el moderador pueda reintentar."""
    ctx = await _crear_contexto()
    pres = ctx["presentacion_id"]
    est = ctx["establecimiento_id"]
    async with sesion_transaccional() as sesion:
        await OficialConContraste().recalcular_par(sesion, pres, est, ctx["ahora"])
    caso = await _caso_abierto(pres, est)
    assert caso is not None

    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("""
                UPDATE public.precio_oficial
                SET precio_cop = 3100, precio_por_base = 3.100000
                WHERE presentacion_id = :pres AND establecimiento_id = :est;
            """),
            {"pres": pres, "est": est},
        )

    with pytest.raises(ConflictoError) as exc:
        await _resolver(caso["id"], "confirmar", ctx["moderador_id"], CacheNula())
    assert "detalle se actualizo" in exc.value.detalle

    assert await _caso_abierto(pres, est) is not None
    async with sesion_transaccional() as sesion:
        detalle = (
            await sesion.execute(
                text("SELECT detalle FROM public.caso_moderacion WHERE id = :id;"),
                {"id": caso["id"]},
            )
        ).scalar_one()
        auditoria = (
            await sesion.execute(
                text("""
                    SELECT count(*) FROM public.auditoria
                    WHERE accion = 'refrescar_detalle_disputa' AND entidad_id = :id;
                """),
                {"id": str(caso["id"])},
            )
        ).scalar_one()
    assert detalle["precio_oficial_cop"] == 3100
    assert detalle["precio_oficial_anterior_cop"] == 3050
    assert detalle["detalle_actualizado_en"]
    assert auditoria == 1

    # El detalle ya coincide: la misma decision ahora resuelve el caso.
    await _resolver(caso["id"], "confirmar", ctx["moderador_id"], CacheNula())

    async with sesion_transaccional() as sesion:
        resuelto = (
            await sesion.execute(
                text("""
                    SELECT estado::text, decision::text
                    FROM public.caso_moderacion WHERE id = :id;
                """),
                {"id": caso["id"]},
            )
        ).first()
        vigente = (
            await sesion.execute(
                text("""
                    SELECT precio_cop, sello::text FROM public.precio_vigente
                    WHERE presentacion_id = :pres AND establecimiento_id = :est;
                """),
                {"pres": pres, "est": est},
            )
        ).first()
    assert resuelto is not None
    assert resuelto.estado == "resuelto"
    assert resuelto.decision == "confirmar"
    assert vigente is not None
    assert vigente.precio_cop == 3100
    assert vigente.sello == "oficial"


@pytest.mark.asyncio
async def test_descartar_con_oficial_inactivo_resuelve_el_caso() -> None:
    """Sin oficial activo la comunidad ya gano: descartar no debe responder 409."""
    ctx = await _crear_contexto()
    pres = ctx["presentacion_id"]
    est = ctx["establecimiento_id"]
    async with sesion_transaccional() as sesion:
        await OficialConContraste().recalcular_par(sesion, pres, est, ctx["ahora"])
    caso = await _caso_abierto(pres, est)
    assert caso is not None

    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("""
                UPDATE public.precio_oficial
                SET activo = false
                WHERE presentacion_id = :pres AND establecimiento_id = :est;
            """),
            {"pres": pres, "est": est},
        )

    await _resolver(caso["id"], "descartar", ctx["moderador_id"], CacheNula())

    async with sesion_transaccional() as sesion:
        resuelto = (
            await sesion.execute(
                text("""
                    SELECT estado::text, decision::text
                    FROM public.caso_moderacion WHERE id = :id;
                """),
                {"id": caso["id"]},
            )
        ).first()
        vigente = (
            await sesion.execute(
                text("""
                    SELECT precio_cop, sello::text FROM public.precio_vigente
                    WHERE presentacion_id = :pres AND establecimiento_id = :est;
                """),
                {"pres": pres, "est": est},
            )
        ).first()
    assert resuelto is not None
    assert resuelto.estado == "resuelto"
    assert resuelto.decision == "descartar"
    assert vigente is not None
    assert vigente.precio_cop == 2600
    assert vigente.sello != "en_disputa"


@pytest.mark.asyncio
async def test_confirmar_con_oficial_inactivo_sigue_siendo_409() -> None:
    """Sin oficial activo no hay nada que confirmar y el caso permanece abierto."""
    ctx = await _crear_contexto()
    pres = ctx["presentacion_id"]
    est = ctx["establecimiento_id"]
    async with sesion_transaccional() as sesion:
        await OficialConContraste().recalcular_par(sesion, pres, est, ctx["ahora"])
    caso = await _caso_abierto(pres, est)
    assert caso is not None

    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("""
                UPDATE public.precio_oficial
                SET activo = false
                WHERE presentacion_id = :pres AND establecimiento_id = :est;
            """),
            {"pres": pres, "est": est},
        )

    with pytest.raises(ConflictoError) as exc:
        await _resolver(caso["id"], "confirmar", ctx["moderador_id"], CacheNula())
    assert "Use 'descartar'" in exc.value.detalle

    assert await _caso_abierto(pres, est) is not None
