"""Pruebas de apelaciones de sanciones y cuentas eliminadas (Ley 1581)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from app.compartido.errores import ConflictoError, NoAutenticadoError
from app.compartido.seguridad import UsuarioAutenticado
from app.modulos.moderacion import repositorio_sanciones
from app.modulos.moderacion import servicio_sanciones as servicio_modulo
from app.modulos.moderacion.esquemas_casos import (
    ApelacionSancionEntrada,
    ResolverApelacionEntrada,
)
from app.modulos.moderacion.servicio_sanciones import ServicioSancionesAuditoria

SANCION_ID = UUID(int=50)
USUARIO_ID = UUID(int=51)
MODERADOR_ID = UUID(int=52)


class _ResultadoFalso:
    """Resultado de SQLAlchemy con una fila opcional."""

    def __init__(self, fila: Any = None) -> None:
        self._fila = fila

    def first(self) -> Any:
        return self._fila


class _SesionFalsa:
    """Sesion que conserva el SQL ejecutado."""

    def __init__(self, fila: Any = None) -> None:
        self.fila = fila
        self.sql = ""

    async def execute(self, sql: Any, parametros: dict[str, Any]) -> _ResultadoFalso:
        self.sql = " ".join(str(sql).lower().split())
        return _ResultadoFalso(self.fila)

    async def flush(self) -> None:
        return None


def _moderador() -> UsuarioAutenticado:
    return UsuarioAutenticado(
        id=MODERADOR_ID,
        email="moderador@armenia.co",
        rol="moderador",
        estado="activa",
    )


def _sancion() -> dict[str, Any]:
    return {
        "id": SANCION_ID,
        "usuario_id": USUARIO_ID,
        "tipo": "suspension",
        "motivo": "Spam continuo",
        "desde": None,
        "hasta": None,
        "apelacion": "Texto de apelacion",
        "apelacion_resuelta": None,
    }


@pytest.mark.asyncio
async def test_actualizar_estado_perfil_no_toca_cuentas_eliminadas() -> None:
    """El UPDATE condicionado devuelve False y nunca reactiva una cuenta eliminada."""
    sesion = _SesionFalsa(fila=None)

    actualizado = await repositorio_sanciones.actualizar_estado_perfil_bd(  # type: ignore[arg-type]
        sesion, USUARIO_ID, "activa", None
    )

    assert actualizado is False
    assert "and estado <> 'eliminada'" in sesion.sql


@pytest.mark.asyncio
async def test_resolver_apelacion_de_eliminada_da_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aprobar la apelacion no puede revivir una cuenta eliminada."""

    async def obtener_sancion(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return _sancion()

    async def resolver_apelacion(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return _sancion()

    async def actualizar_estado(*args: Any, **kwargs: Any) -> bool:
        return False

    async def auditoria(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        servicio_modulo.repositorio_sanciones, "obtener_sancion_por_id_bd", obtener_sancion
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio_sanciones, "resolver_apelacion_bd", resolver_apelacion
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio_sanciones, "actualizar_estado_perfil_bd", actualizar_estado
    )
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", auditoria)

    servicio = ServicioSancionesAuditoria(sesion=object())  # type: ignore[arg-type]
    with pytest.raises(ConflictoError, match="no puede reactivarla") as exc:
        await servicio.resolver_apelacion(
            SANCION_ID,
            ResolverApelacionEntrada(aprobar=True, nota="Apelacion aceptada"),
            _moderador(),
        )

    assert exc.value.status == 409


@pytest.mark.asyncio
async def test_registrar_apelacion_de_eliminada_da_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El servicio tambien rechaza la apelacion si la dependencia base no lo hizo."""

    async def no_debe_consultar(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("No debe consultar la sancion de una cuenta eliminada.")

    monkeypatch.setattr(
        servicio_modulo.repositorio_sanciones,
        "obtener_sancion_por_id_bd",
        no_debe_consultar,
    )
    servicio = ServicioSancionesAuditoria(sesion=object())  # type: ignore[arg-type]
    usuario = UsuarioAutenticado(
        id=USUARIO_ID,
        email="eliminado@armenia.co",
        rol="reportante",
        estado="eliminada",
    )

    with pytest.raises(NoAutenticadoError) as exc:
        await servicio.registrar_apelacion(
            SANCION_ID,
            ApelacionSancionEntrada(apelacion="Quiero apelar esta sancion."),
            usuario,
        )

    assert exc.value.status == 401


@pytest.mark.asyncio
async def test_resolver_apelacion_aprobada_reactiva_cuenta_activa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El camino feliz sigue reactivando una cuenta no eliminada."""

    async def obtener_sancion(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return _sancion()

    async def resolver_apelacion(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return _sancion()

    async def actualizar_estado(*args: Any, **kwargs: Any) -> bool:
        return True

    async def auditoria(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        servicio_modulo.repositorio_sanciones, "obtener_sancion_por_id_bd", obtener_sancion
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio_sanciones, "resolver_apelacion_bd", resolver_apelacion
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio_sanciones, "actualizar_estado_perfil_bd", actualizar_estado
    )
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", auditoria)

    servicio = ServicioSancionesAuditoria(sesion=_SesionFalsa())  # type: ignore[arg-type]
    await servicio.resolver_apelacion(
        SANCION_ID,
        ResolverApelacionEntrada(aprobar=True, nota="Apelacion aceptada"),
        _moderador(),
    )
