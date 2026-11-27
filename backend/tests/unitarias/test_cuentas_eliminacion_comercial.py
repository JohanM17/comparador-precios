"""Pruebas unitarias de la limpieza comercial al ejercer el derecho de supresion.

La prueba de integracion contra PostgreSQL vive en
`tests/integracion/test_cuentas_ley1581.py`; estas pruebas usan una sesion falsa
para verificar el SQL y, sobre todo, que la auditoria no conserve PII.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.compartido.seguridad import UsuarioAutenticado
from app.modulos.cuentas import repositorio
from app.modulos.cuentas import servicio as servicio_modulo
from app.modulos.cuentas.servicio import ServicioCuentas

USUARIO_ID = UUID(int=30)


def _sql_normalizado(sentencia: Any) -> str:
    """Normaliza espacios y mayusculas para comparar fragmentos de SQL."""
    return " ".join(str(sentencia).lower().split())


class _ResultadoFalso:
    """Resultado de SQLAlchemy con filas o una fila ya preparadas."""

    def __init__(self, filas: list[Any] | None = None, fila: Any = None) -> None:
        self._filas = filas or []
        self._fila = fila

    def fetchall(self) -> list[Any]:
        return self._filas

    def fetchone(self) -> Any:
        return self._fila


class _SesionGuion:
    """Sesion que entrega resultados en el orden exacto de las consultas."""

    def __init__(self, resultados: list[_ResultadoFalso]) -> None:
        self.resultados = list(resultados)
        self.llamadas: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, sql: Any, parametros: dict[str, Any]) -> _ResultadoFalso:
        self.llamadas.append((_sql_normalizado(sql), parametros))
        return self.resultados.pop(0)


@pytest.mark.asyncio
async def test_anonimizar_limpia_reclamos_tiendas_precios_y_promociones() -> None:
    """La baja desvincula lo comercial y no deja telefono ni mensaje en reclamos."""
    est_a, est_b = uuid4(), uuid4()
    sesion = _SesionGuion(
        [
            _ResultadoFalso(filas=[]),  # fotos del reportante
            _ResultadoFalso(),  # anonimizar reportes
            _ResultadoFalso(
                fila=SimpleNamespace(
                    _mapping={
                        "id": USUARIO_ID,
                        "alias": "eliminado_00000000",
                        "estado": "eliminada",
                    }
                )
            ),  # perfil
            _ResultadoFalso(),  # revocar autorizacion
            _ResultadoFalso(filas=[SimpleNamespace(id=uuid4())]),  # borrar pendientes
            _ResultadoFalso(filas=[SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]),
            _ResultadoFalso(filas=[SimpleNamespace(id=est_a), SimpleNamespace(id=est_b)]),
            _ResultadoFalso(filas=[SimpleNamespace(presentacion_id=uuid4()) for _ in range(3)]),
            _ResultadoFalso(filas=[SimpleNamespace(id=uuid4())]),
        ]
    )

    perfil, rutas, resumen = await repositorio.anonimizar_y_dar_de_baja_cuenta(  # type: ignore[arg-type]
        sesion, USUARIO_ID
    )

    assert perfil["estado"] == "eliminada"
    assert rutas == []
    assert resumen == {
        "reclamos_pendientes_borrados": 1,
        "reclamos_anonimizados": 2,
        "establecimientos_desvinculados": 2,
        "precios_oficiales_desactivados": 3,
        "promociones_revocadas": 1,
    }

    sqls = [sql for sql, _ in sesion.llamadas]
    assert any(
        sql.startswith("delete from solicitud_verificacion_comercio")
        and "estado = 'pendiente'" in sql
        for sql in sqls
    )
    assert any("set telefono_contacto = :telefono, mensaje = :mensaje" in sql for sql in sqls)
    assert any(
        "set comercio_id = null" in sql and "estado_verificacion = 'sin_dueno'" in sql
        for sql in sqls
    )
    assert any("update precio_oficial set activo = false" in sql for sql in sqls)
    assert any("update promocion set activa = false, revocada_en = now()" in sql for sql in sqls)

    parametros_reclamos = next(
        params for sql, params in sesion.llamadas if "set telefono_contacto = :telefono" in sql
    )
    assert parametros_reclamos["telefono"] == "anonimizado"
    assert "Ley 1581" in parametros_reclamos["mensaje"]

    parametros_desvinculacion = next(
        params for sql, params in sesion.llamadas if "set comercio_id = null" in sql
    )
    assert parametros_desvinculacion == {"id": USUARIO_ID}

    parametros_precios = next(
        params for sql, params in sesion.llamadas if "update precio_oficial" in sql
    )
    assert parametros_precios["establecimientos"] == [est_a, est_b]


@pytest.mark.asyncio
async def test_sin_tiendas_no_ejecuta_updates_comerciales() -> None:
    """Un usuario sin establecimientos no dispara updates vacios de precios/promos."""
    sesion = _SesionGuion(
        [
            _ResultadoFalso(filas=[]),
            _ResultadoFalso(),
            _ResultadoFalso(
                fila=SimpleNamespace(
                    _mapping={
                        "id": USUARIO_ID,
                        "alias": "eliminado_00000000",
                        "estado": "eliminada",
                    }
                )
            ),
            _ResultadoFalso(),
            _ResultadoFalso(filas=[]),
            _ResultadoFalso(filas=[]),
            _ResultadoFalso(filas=[]),
        ]
    )

    _, _, resumen = await repositorio.anonimizar_y_dar_de_baja_cuenta(  # type: ignore[arg-type]
        sesion, USUARIO_ID
    )

    assert resumen["establecimientos_desvinculados"] == 0
    assert resumen["precios_oficiales_desactivados"] == 0
    assert resumen["promociones_revocadas"] == 0
    assert not any(
        sql.startswith("update precio_oficial") or sql.startswith("update promocion")
        for sql, _ in sesion.llamadas
    )


@pytest.mark.asyncio
async def test_la_auditoria_de_la_baja_no_guarda_pii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El alias anterior, el telefono y el mensaje no llegan a la auditoria."""
    usuario = UsuarioAutenticado(
        id=USUARIO_ID,
        email="titular@armenia.co",
        rol="comercio",
        estado="activa",
    )
    perfil_previo = {
        "id": USUARIO_ID,
        "alias": "tendero_original",
        "estado": "activa",
        "autorizacion_vigente": {"version_politica": "1.0"},
    }
    resumen = {
        "reclamos_pendientes_borrados": 1,
        "reclamos_anonimizados": 1,
        "establecimientos_desvinculados": 1,
        "precios_oficiales_desactivados": 2,
        "promociones_revocadas": 1,
    }
    capturado: dict[str, Any] = {}

    async def obtener_perfil(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return perfil_previo

    async def anonimizar(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], list[str], Any]:
        return (
            {"id": USUARIO_ID, "alias": "eliminado_00000000", "estado": "eliminada"},
            [],
            resumen,
        )

    async def registrar_auditoria(*args: Any, **kwargs: Any) -> None:
        capturado.update(kwargs)

    monkeypatch.setattr(servicio_modulo, "obtener_perfil_con_autorizacion", obtener_perfil)
    monkeypatch.setattr(servicio_modulo, "anonimizar_y_dar_de_baja_cuenta", anonimizar)
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", registrar_auditoria)

    servicio = ServicioCuentas(sesion=object())  # type: ignore[arg-type]
    respuesta = await servicio.eliminar_mi_cuenta(usuario)

    assert respuesta.estado == "eliminada"
    assert capturado["antes"] == {"estado": "activa"}
    assert capturado["despues"] == {
        "id": USUARIO_ID,
        "alias": "eliminado_00000000",
        "estado": "eliminada",
        **resumen,
    }
    texto_auditoria = str(capturado)
    assert "tendero_original" not in texto_auditoria
    assert "3001234567" not in texto_auditoria
    assert "Soy el dueno" not in texto_auditoria
