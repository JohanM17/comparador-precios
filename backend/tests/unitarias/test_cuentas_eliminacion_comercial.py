"""Pruebas unitarias de la limpieza comercial al ejercer el derecho de supresion.

La prueba de integracion contra PostgreSQL vive en
`tests/integracion/test_cuentas_ley1581.py`; estas pruebas usan una sesion falsa
para verificar el SQL, el orden de bloqueos, la invalidacion de cache y que la
auditoria no conserve PII.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.compartido.errores import ConflictoError
from app.compartido.seguridad import UsuarioAutenticado
from app.modulos.cuentas import repositorio
from app.modulos.cuentas import servicio as servicio_modulo
from app.modulos.cuentas.esquemas import ActualizarAliasEntrada
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
async def test_anonimizar_limpia_comercial_y_elimina_precio_vigente() -> None:
    """La baja desvincula, apaga precios/promos y borra la proyeccion oficial."""
    est_a, est_b = uuid4(), uuid4()
    prod_comun = uuid4()
    prod_promo = uuid4()
    prod_vigente = uuid4()
    sesion = _SesionGuion(
        [
            _ResultadoFalso(),  # advisory lock por usuario
            _ResultadoFalso(filas=[]),  # fotos del reportante
            _ResultadoFalso(),  # anonimizar reportes
            _ResultadoFalso(filas=[SimpleNamespace(id=uuid4())]),  # borrar pendientes
            _ResultadoFalso(filas=[SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]),
            _ResultadoFalso(filas=[SimpleNamespace(id=uuid4())]),  # sancion.apelacion
            _ResultadoFalso(filas=[SimpleNamespace(id=est_a), SimpleNamespace(id=est_b)]),
            _ResultadoFalso(
                filas=[
                    SimpleNamespace(producto_id=prod_comun),
                    SimpleNamespace(producto_id=prod_comun),
                    SimpleNamespace(producto_id=prod_vigente),
                ]
            ),
            _ResultadoFalso(filas=[SimpleNamespace(producto_id=prod_promo)]),
            _ResultadoFalso(
                filas=[
                    SimpleNamespace(producto_id=prod_comun),
                    SimpleNamespace(producto_id=prod_vigente),
                ]
            ),
            _ResultadoFalso(
                fila=SimpleNamespace(
                    _mapping={
                        "id": USUARIO_ID,
                        "alias": "eliminado_00000000",
                        "estado": "eliminada",
                        "rol": "reportante",
                    }
                )
            ),
            _ResultadoFalso(),  # revocar autorizacion
        ]
    )

    perfil, rutas, resumen, productos = await repositorio.anonimizar_y_dar_de_baja_cuenta(  # type: ignore[arg-type]
        sesion, USUARIO_ID
    )

    assert perfil["estado"] == "eliminada"
    assert perfil["rol"] == "reportante"
    assert rutas == []
    assert productos == sorted({prod_comun, prod_promo, prod_vigente})
    assert resumen == {
        "reclamos_pendientes_borrados": 1,
        "reclamos_anonimizados": 2,
        "establecimientos_desvinculados": 2,
        "precios_oficiales_desactivados": 3,
        "promociones_revocadas": 1,
        "precios_vigentes_eliminados": 2,
        "apelaciones_anonimizadas": 1,
    }

    sqls = [sql for sql, _ in sesion.llamadas]
    assert sqls[0].startswith("select pg_advisory_xact_lock")
    assert any("update sancion set apelacion = null" in sql for sql in sqls)
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
    assert any("delete from precio_vigente" in sql for sql in sqls)

    indice_reclamo = next(
        i
        for i, sql in enumerate(sqls)
        if sql.startswith("delete from solicitud_verificacion_comercio")
    )
    indice_sancion = next(i for i, sql in enumerate(sqls) if sql.startswith("update sancion"))
    indice_tienda = next(i for i, sql in enumerate(sqls) if "set comercio_id = null" in sql)
    indice_precio = next(i for i, sql in enumerate(sqls) if sql.startswith("update precio_oficial"))
    indice_promo = next(i for i, sql in enumerate(sqls) if sql.startswith("update promocion"))
    indice_vigente = next(
        i for i, sql in enumerate(sqls) if sql.startswith("delete from precio_vigente")
    )
    indice_perfil = next(i for i, sql in enumerate(sqls) if sql.startswith("update perfil"))
    assert (
        indice_reclamo
        < indice_sancion
        < indice_tienda
        < indice_precio
        < indice_promo
        < indice_vigente
        < indice_perfil
    )
    assert "rol = 'reportante'" in sqls[indice_perfil]

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
            _ResultadoFalso(),
            _ResultadoFalso(filas=[]),
            _ResultadoFalso(),
            _ResultadoFalso(filas=[]),
            _ResultadoFalso(filas=[]),
            _ResultadoFalso(filas=[]),
            _ResultadoFalso(filas=[]),
            _ResultadoFalso(
                fila=SimpleNamespace(
                    _mapping={
                        "id": USUARIO_ID,
                        "alias": "eliminado_00000000",
                        "estado": "eliminada",
                        "rol": "reportante",
                    }
                )
            ),
            _ResultadoFalso(),
        ]
    )

    _, _, resumen, productos = await repositorio.anonimizar_y_dar_de_baja_cuenta(  # type: ignore[arg-type]
        sesion, USUARIO_ID
    )

    assert productos == []
    assert resumen["establecimientos_desvinculados"] == 0
    assert resumen["precios_oficiales_desactivados"] == 0
    assert resumen["promociones_revocadas"] == 0
    assert resumen["precios_vigentes_eliminados"] == 0
    assert not any(
        sql.startswith("update precio_oficial")
        or sql.startswith("update promocion")
        or sql.startswith("delete from precio_vigente")
        for sql, _ in sesion.llamadas
    )


class _CacheFalsa:
    """Cache que registra las invalidaciones recibidas."""

    def __init__(self, eventos: list[str]) -> None:
        self.eventos = eventos
        self.productos: list[UUID] = []

    async def invalidar_producto(self, producto_id: UUID) -> None:
        self.eventos.append(f"cache:{producto_id}")
        self.productos.append(producto_id)


@pytest.mark.asyncio
async def test_la_baja_audita_sin_pii_e_invalida_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La auditoria no guarda PII y la cache se invalida despues de la BD."""
    usuario = UsuarioAutenticado(
        id=USUARIO_ID,
        email="titular@armenia.co",
        rol="comercio",
        estado="activa",
    )
    eventos: list[str] = []
    productos = [uuid4(), uuid4()]
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
        "precios_vigentes_eliminados": 2,
        "apelaciones_anonimizadas": 1,
    }
    capturado: dict[str, Any] = {}

    async def obtener_perfil(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return perfil_previo

    async def anonimizar(
        *args: Any, **kwargs: Any
    ) -> tuple[dict[str, Any], list[str], dict[str, int], list[UUID]]:
        eventos.append("bd")
        return (
            {
                "id": USUARIO_ID,
                "alias": "eliminado_00000000",
                "estado": "eliminada",
                "rol": "reportante",
            },
            [],
            resumen,
            productos,
        )

    async def registrar_auditoria(*args: Any, **kwargs: Any) -> None:
        eventos.append("auditoria")
        capturado.update(kwargs)

    monkeypatch.setattr(servicio_modulo, "obtener_perfil_con_autorizacion", obtener_perfil)
    monkeypatch.setattr(servicio_modulo, "anonimizar_y_dar_de_baja_cuenta", anonimizar)
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", registrar_auditoria)

    cache = _CacheFalsa(eventos)
    servicio = ServicioCuentas(sesion=object(), puerto_cache=cache)  # type: ignore[arg-type]
    respuesta = await servicio.eliminar_mi_cuenta(usuario)
    assert respuesta.estado == "eliminada"
    assert eventos == ["bd", "auditoria"]
    assert cache.productos == []

    await servicio.invalidar_cache_baja()
    assert eventos == ["bd", "auditoria", f"cache:{productos[0]}", f"cache:{productos[1]}"]
    assert cache.productos == productos
    assert capturado["antes"] == {"estado": "activa"}
    assert capturado["despues"] == {
        "id": USUARIO_ID,
        "alias": "eliminado_00000000",
        "estado": "eliminada",
        "rol": "reportante",
        **resumen,
    }
    texto_auditoria = str(capturado)
    assert "tendero_original" not in texto_auditoria
    assert "3001234567" not in texto_auditoria
    assert "Soy el dueno" not in texto_auditoria


@pytest.mark.asyncio
async def test_la_baja_sin_cache_no_falla() -> None:
    """Sin puerto de cache la baja sigue funcionando."""
    servicio = ServicioCuentas(sesion=object())  # type: ignore[arg-type]
    assert servicio.puerto_cache is None
    await servicio.invalidar_cache_baja()


@pytest.mark.asyncio
async def test_crear_o_actualizar_autorizacion_rechaza_perfil_eliminado() -> None:
    """El upsert no reactiva un perfil eliminado y no escribe la autorizacion."""
    sesion = _SesionGuion([_ResultadoFalso(fila=None)])

    with pytest.raises(ConflictoError, match="no puede reactivarse"):
        await repositorio.crear_o_actualizar_autorizacion(  # type: ignore[arg-type]
            sesion,
            USUARIO_ID,
            "alias_nuevo",
            "1.0",
            "Finalidad de prueba",
        )

    assert len(sesion.llamadas) == 1
    assert "where perfil.estado <> 'eliminada'" in sesion.llamadas[0][0]


@pytest.mark.asyncio
async def test_actualizar_alias_bd_solo_toca_cuentas_activas() -> None:
    """La actualizacion de alias filtra por estado activo y devuelve None si no aplica."""
    sesion = _SesionGuion([_ResultadoFalso(fila=None)])

    resultado = await repositorio.actualizar_alias_bd(  # type: ignore[arg-type]
        sesion, USUARIO_ID, "alias_nuevo"
    )

    assert resultado is None
    assert "and estado = 'activa'" in sesion.llamadas[0][0]


@pytest.mark.asyncio
async def test_actualizar_alias_de_cuenta_eliminada_devuelve_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aunque el perfil previo exista, un update sin fila termina en 409."""
    usuario = UsuarioAutenticado(
        id=USUARIO_ID,
        email="titular@armenia.co",
        rol="comercio",
        estado="activa",
    )

    async def obtener_perfil(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "id": USUARIO_ID,
            "alias": "tendero_original",
            "estado": "eliminada",
            "autorizacion_vigente": {"version_politica": "1.0"},
        }

    async def alias_libre(*args: Any, **kwargs: Any) -> bool:
        return True

    async def alias_no_aplica(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(servicio_modulo, "obtener_perfil_con_autorizacion", obtener_perfil)
    monkeypatch.setattr(servicio_modulo, "verificar_alias_disponible", alias_libre)
    monkeypatch.setattr(servicio_modulo, "actualizar_alias_bd", alias_no_aplica)

    servicio = ServicioCuentas(sesion=object())  # type: ignore[arg-type]
    with pytest.raises(ConflictoError, match="ya no esta activa"):
        await servicio.actualizar_mi_alias(usuario, ActualizarAliasEntrada(alias="alias_nuevo"))
