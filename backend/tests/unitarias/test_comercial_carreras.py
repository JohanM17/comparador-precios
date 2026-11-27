"""Pruebas unitarias de las carreras de titularidad comercial (D-09).

No tocan PostgreSQL: la sesion y el repositorio del servicio se sustituyen por
dobles. Lo que se verifica es la decision de negocio ante dos moderadores o dos
comercios que intentan ganar la misma fila al mismo tiempo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.compartido.bloqueos import bloquear_por_usuario
from app.compartido.errores import ConflictoError, NoAutenticadoError
from app.compartido.seguridad import UsuarioAutenticado
from app.modulos.comercial import repositorio
from app.modulos.comercial import servicio as servicio_modulo
from app.modulos.comercial.esquemas import (
    PromocionEntrada,
    ReclamoComercioEntrada,
    VerificarComercioEntrada,
)
from app.modulos.comercial.servicio import ServicioComercial

ESTABLECIMIENTO_ID = UUID(int=10)
COMERCIO_ID = UUID(int=11)
SOLICITUD_ID = UUID(int=12)
MODERADOR = UsuarioAutenticado(
    id=UUID(int=13),
    email="moderador@armenia.co",
    rol="moderador",
    estado="activa",
)
SOLICITANTE = UsuarioAutenticado(
    id=COMERCIO_ID,
    email="comercio@armenia.co",
    rol="reportante",
    estado="activa",
)


def _sql_normalizado(sentencia: Any) -> str:
    """Normaliza espacios y mayusculas para comparar fragmentos de SQL."""
    return " ".join(str(sentencia).lower().split())


class _ResultadoFalso:
    """Resultado de SQLAlchemy con una fila opcional."""

    def __init__(self, fila: Any = None) -> None:
        self._fila = fila

    def first(self) -> Any:
        return self._fila

    def fetchall(self) -> list[Any]:
        return [] if self._fila is None else [self._fila]


class _TransaccionFalsa:
    """SAVEPOINT falso para las pruebas del servicio."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: Any) -> bool:
        return False


class _SesionFalsa:
    """Sesion minima que conserva el SQL y los parametros ejecutados."""

    def __init__(self, fila: Any = None) -> None:
        self.fila = fila
        self.sql = ""
        self.parametros: dict[str, Any] = {}

    def begin_nested(self) -> _TransaccionFalsa:
        return _TransaccionFalsa()

    async def execute(self, sql: Any, parametros: dict[str, Any]) -> _ResultadoFalso:
        self.sql = str(sql)
        self.parametros = parametros
        return _ResultadoFalso(self.fila)


@pytest.mark.asyncio
async def test_el_bloqueo_por_usuario_es_advisory_transaccional() -> None:
    """Baja y reclamo comparten la misma clave advisory por titular."""
    sesion = _SesionFalsa()

    await bloquear_por_usuario(sesion, COMERCIO_ID)  # type: ignore[arg-type]

    assert "select pg_advisory_xact_lock(hashtext(:usuario_id_texto))" in _sql_normalizado(
        sesion.sql
    )
    assert sesion.parametros == {"usuario_id_texto": str(COMERCIO_ID)}


@pytest.mark.asyncio
async def test_obtener_solicitud_bloquea_la_fila_para_resolver() -> None:
    """La lectura de la solicitud toma `FOR UPDATE` antes de decidir."""
    sesion = _SesionFalsa(
        SimpleNamespace(
            _mapping={
                "id": SOLICITUD_ID,
                "usuario_id": COMERCIO_ID,
                "establecimiento_id": ESTABLECIMIENTO_ID,
                "estado": "pendiente",
                "creado_en": None,
            }
        )
    )

    solicitud = await repositorio.obtener_solicitud(sesion, SOLICITUD_ID)  # type: ignore[arg-type]

    assert solicitud is not None
    assert "for update" in _sql_normalizado(sesion.sql)
    assert sesion.parametros == {"id": SOLICITUD_ID}


def test_resolver_solicitud_solo_actualiza_pendientes() -> None:
    """El UPDATE condicional impide que una solicitud resuelta se reescriba."""
    sql = _sql_normalizado(repositorio._SQL_RESOLVER_SOLICITUD_PENDIENTE)

    assert "where id = :id and estado = 'pendiente'" in sql
    assert "returning id" in sql


@pytest.mark.asyncio
async def test_resolver_solicitud_devuelve_false_si_ya_fue_resuelta() -> None:
    """Sin fila devuelta, el servicio sabe que perdio la carrera y responde 409."""
    sesion = _SesionFalsa(None)

    resuelta = await repositorio.resolver_solicitud(  # type: ignore[arg-type]
        sesion, SOLICITUD_ID, MODERADOR.id, True
    )

    assert resuelta is False


def test_enlazar_comercio_solo_toma_tiendas_sin_dueno() -> None:
    """El UPDATE condicional impide pisar al dueno que gano primero."""
    sql = _sql_normalizado(repositorio._SQL_ENLAZAR_ESTABLECIMIENTO_LIBRE)

    assert "where id = :est_id and comercio_id is null" in sql
    assert "returning id" in sql


@pytest.mark.asyncio
async def test_enlazar_comercio_devuelve_false_si_la_tienda_ya_tiene_dueno() -> None:
    """Sin fila devuelta, la aprobacion pierde y el servicio responde 409."""
    sesion = _SesionFalsa(None)

    enlazado = await repositorio.enlazar_comercio(  # type: ignore[arg-type]
        sesion, ESTABLECIMIENTO_ID, COMERCIO_ID
    )

    assert enlazado is False


class _RepositorioEstado:
    """Doble que conserva el estado de la solicitud como lo haria la base."""

    def __init__(self) -> None:
        self.estado = "pendiente"
        self.resoluciones = 0
        self.enlaces = 0
        self.roles = 0

    async def obtener_solicitud(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "id": SOLICITUD_ID,
            "usuario_id": COMERCIO_ID,
            "establecimiento_id": ESTABLECIMIENTO_ID,
            "estado": self.estado,
            "creado_en": None,
        }

    async def resolver_solicitud(self, *args: Any, **kwargs: Any) -> bool:
        # Igual que el UPDATE condicional: solo la primera resolucion devuelve fila.
        if self.estado != "pendiente" or self.resoluciones > 0:
            return False
        aprobada = args[3] if len(args) > 3 else kwargs.get("aprobada", True)
        self.estado = "verificado" if aprobada else "sin_dueno"
        self.resoluciones += 1
        return True

    async def enlazar_comercio(self, *args: Any, **kwargs: Any) -> bool:
        self.enlaces += 1
        return True

    async def asignar_rol_comercio(self, *args: Any, **kwargs: Any) -> None:
        self.roles += 1


def _instalar_repositorio(
    monkeypatch: pytest.MonkeyPatch,
    repo: _RepositorioEstado,
) -> None:
    async def registrar_auditoria(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(servicio_modulo.repositorio, "obtener_solicitud", repo.obtener_solicitud)
    monkeypatch.setattr(servicio_modulo.repositorio, "resolver_solicitud", repo.resolver_solicitud)
    monkeypatch.setattr(servicio_modulo.repositorio, "enlazar_comercio", repo.enlazar_comercio)
    monkeypatch.setattr(
        servicio_modulo.repositorio, "asignar_rol_comercio", repo.asignar_rol_comercio
    )
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", registrar_auditoria)


class _CacheFalsa:
    """Cache que registra las invalidaciones."""

    def __init__(self) -> None:
        self.productos: list[UUID] = []

    async def invalidar_producto(self, producto_id: UUID) -> None:
        self.productos.append(producto_id)


def _servicio() -> ServicioComercial:
    return ServicioComercial(sesion=_SesionFalsa(), puerto_cache=_CacheFalsa())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_doble_resolucion_solo_aprueba_una_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dos moderadores resuelven la misma solicitud: el segundo recibe 409."""
    repo = _RepositorioEstado()
    _instalar_repositorio(monkeypatch, repo)
    servicio = _servicio()
    entrada = VerificarComercioEntrada(aprobar=True)

    primera = await servicio.verificar_comercio(SOLICITUD_ID, entrada, MODERADOR)
    with pytest.raises(ConflictoError, match="ya fue resuelta") as exc:
        await servicio.verificar_comercio(SOLICITUD_ID, entrada, MODERADOR)

    assert exc.value.codigo == "CONFLICTO"
    assert primera["estado"] == "verificado"
    assert repo.resoluciones == 1
    assert repo.enlaces == 1
    assert repo.roles == 1


@pytest.mark.asyncio
async def test_doble_aprobacion_pierde_si_el_update_condicional_no_aplica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aunque ambos lean `pendiente`, solo el UPDATE que devuelve fila sigue."""
    repo = _RepositorioEstado()
    _instalar_repositorio(monkeypatch, repo)
    servicio = _servicio()
    entrada = VerificarComercioEntrada(aprobar=True)

    # El primero gana y marca la solicitud. El segundo simula la lectura obsoleta
    # al forzar el estado de vuelta a `pendiente`; el UPDATE condicional lo frena.
    await servicio.verificar_comercio(SOLICITUD_ID, entrada, MODERADOR)
    repo.estado = "pendiente"

    # El doble ya no deja resolver dos veces, igual que el UPDATE real.
    with pytest.raises(ConflictoError, match="ya fue resuelta"):
        await servicio.verificar_comercio(SOLICITUD_ID, entrada, MODERADOR)

    assert repo.resoluciones == 1
    assert repo.enlaces == 1


@pytest.mark.asyncio
async def test_aprobacion_que_pierde_la_tienda_no_asigna_rol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si otro comercio tomo la tienda, no se eleva el rol del que llego tarde."""
    repo = _RepositorioEstado()

    async def enlazar_ocupado(*args: Any, **kwargs: Any) -> bool:
        repo.enlaces += 1
        return False

    _instalar_repositorio(monkeypatch, repo)
    monkeypatch.setattr(servicio_modulo.repositorio, "enlazar_comercio", enlazar_ocupado)
    servicio = _servicio()

    with pytest.raises(ConflictoError, match="ya tiene un dueno") as exc:
        await servicio.verificar_comercio(
            SOLICITUD_ID, VerificarComercioEntrada(aprobar=True), MODERADOR
        )

    assert exc.value.codigo == "CONFLICTO"
    assert repo.resoluciones == 1
    assert repo.enlaces == 1
    assert repo.roles == 0


@pytest.mark.asyncio
async def test_reclamo_simultaneo_traduce_integrity_error_en_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El indice unico parcial cierra la carrera; el perdedor recibe 409, no 500."""
    entrada = ReclamoComercioEntrada(
        establecimiento_id=ESTABLECIMIENTO_ID,
        telefono_contacto="3001234567",
        mensaje="Soy el dueno de la tienda y atiendo de 7 a 8.",
    )

    async def obtener_establecimiento(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "id": ESTABLECIMIENTO_ID,
            "nombre": "Tienda sin dueno",
            "tipo": "tienda_barrio",
            "barrio": None,
            "direccion": None,
            "comercio_id": None,
            "estado_verificacion": "sin_dueno",
            "activo": True,
        }

    async def existe_reclamo_abierto(*args: Any, **kwargs: Any) -> bool:
        return False

    async def crear_reclamo(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise IntegrityError("INSERT", {}, Exception("duplicate key value"))

    async def bloquear_establecimiento(*args: Any, **kwargs: Any) -> None:
        return None

    async def bloquear_por_usuario(*args: Any, **kwargs: Any) -> None:
        return None

    async def usuario_puede_reclamar(*args: Any, **kwargs: Any) -> bool:
        return True

    async def auditoria_inesperada(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Un reclamo rechazado no debe auditarse como creado.")

    monkeypatch.setattr(servicio_modulo, "bloquear_por_usuario", bloquear_por_usuario)
    monkeypatch.setattr(
        servicio_modulo.repositorio, "usuario_puede_reclamar", usuario_puede_reclamar
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "bloquear_establecimiento", bloquear_establecimiento
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "obtener_establecimiento", obtener_establecimiento
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "existe_reclamo_abierto", existe_reclamo_abierto
    )
    monkeypatch.setattr(servicio_modulo.repositorio, "crear_reclamo", crear_reclamo)
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", auditoria_inesperada)
    servicio = _servicio()

    with pytest.raises(ConflictoError, match="Ya hay un reclamo") as exc:
        await servicio.reclamar_titularidad(entrada, SOLICITANTE)

    assert exc.value.codigo == "CONFLICTO"


@pytest.mark.asyncio
async def test_reclamar_bloquea_antes_de_comprobar_propiedad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El lock de la tienda se toma antes de leer dueno y reclamo abierto."""
    eventos: list[str] = []
    entrada = ReclamoComercioEntrada(
        establecimiento_id=ESTABLECIMIENTO_ID,
        telefono_contacto="3001234567",
        mensaje="Soy el dueno de la tienda y atiendo de 7 a 8.",
    )

    async def bloquear_por_usuario(*args: Any, **kwargs: Any) -> None:
        eventos.append("advisory")

    async def usuario_puede_reclamar(*args: Any, **kwargs: Any) -> bool:
        eventos.append("estado")
        return True

    async def bloquear_establecimiento(*args: Any, **kwargs: Any) -> None:
        eventos.append("lock")

    async def obtener_establecimiento(*args: Any, **kwargs: Any) -> dict[str, Any]:
        eventos.append("leer")
        return {
            "id": ESTABLECIMIENTO_ID,
            "nombre": "Tienda sin dueno",
            "tipo": "tienda_barrio",
            "barrio": None,
            "direccion": None,
            "comercio_id": None,
            "estado_verificacion": "sin_dueno",
            "activo": True,
        }

    async def existe_reclamo_abierto(*args: Any, **kwargs: Any) -> bool:
        eventos.append("reclamo")
        return False

    async def crear_reclamo(*args: Any, **kwargs: Any) -> dict[str, Any]:
        eventos.append("insert")
        return {
            "id": uuid4(),
            "establecimiento_id": ESTABLECIMIENTO_ID,
            "estado": "pendiente",
            "creado_en": None,
        }

    async def registrar_auditoria(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(servicio_modulo, "bloquear_por_usuario", bloquear_por_usuario)
    monkeypatch.setattr(
        servicio_modulo.repositorio, "usuario_puede_reclamar", usuario_puede_reclamar
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "bloquear_establecimiento", bloquear_establecimiento
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "obtener_establecimiento", obtener_establecimiento
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "existe_reclamo_abierto", existe_reclamo_abierto
    )
    monkeypatch.setattr(servicio_modulo.repositorio, "crear_reclamo", crear_reclamo)
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", registrar_auditoria)
    servicio = _servicio()

    await servicio.reclamar_titularidad(entrada, SOLICITANTE)

    assert eventos == ["advisory", "estado", "lock", "leer", "reclamo", "insert"]


@pytest.mark.asyncio
async def test_reclamo_rechaza_cuenta_eliminada_tras_el_advisory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si la baja gano el advisory, el reclamo ve el perfil eliminado y no inserta."""
    eventos: list[str] = []
    entrada = ReclamoComercioEntrada(
        establecimiento_id=ESTABLECIMIENTO_ID,
        telefono_contacto="3001234567",
        mensaje="Soy el dueno de la tienda y atiendo de 7 a 8.",
    )

    async def bloquear_por_usuario(*args: Any, **kwargs: Any) -> None:
        eventos.append("advisory")

    async def usuario_puede_reclamar(*args: Any, **kwargs: Any) -> bool:
        eventos.append("estado")
        return False

    async def bloquear_establecimiento(*args: Any, **kwargs: Any) -> None:
        eventos.append("lock")

    async def crear_reclamo(*args: Any, **kwargs: Any) -> dict[str, Any]:
        eventos.append("insert")
        return {}

    monkeypatch.setattr(servicio_modulo, "bloquear_por_usuario", bloquear_por_usuario)
    monkeypatch.setattr(
        servicio_modulo.repositorio, "usuario_puede_reclamar", usuario_puede_reclamar
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "bloquear_establecimiento", bloquear_establecimiento
    )
    monkeypatch.setattr(servicio_modulo.repositorio, "crear_reclamo", crear_reclamo)
    servicio = _servicio()

    with pytest.raises(NoAutenticadoError) as exc:
        await servicio.reclamar_titularidad(entrada, SOLICITANTE)

    assert exc.value.status == 401
    assert eventos == ["advisory", "estado"]


@pytest.mark.asyncio
async def test_crear_promocion_bloquea_antes_de_comprobar_propiedad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La promocion no puede nacer si una baja o aprobacion cambia el dueno."""
    eventos: list[str] = []
    producto_id = uuid4()
    entrada = PromocionEntrada(
        producto_id=producto_id,
        titulo="Descuento de prueba",
        tipo="porcentaje",
        porcentaje_descuento=20,
        condiciones="Valida en la sede del centro hasta agotar unidades.",
        vigente_desde=datetime.now(UTC),
        vigente_hasta=datetime.now(UTC) + timedelta(days=1),
        hasta_revocar=False,
    )

    async def bloquear_establecimiento(*args: Any, **kwargs: Any) -> None:
        eventos.append("lock")

    async def obtener_establecimiento(*args: Any, **kwargs: Any) -> dict[str, Any]:
        eventos.append("autorizacion")
        return {
            "id": ESTABLECIMIENTO_ID,
            "nombre": "Tienda propia",
            "tipo": "tienda_barrio",
            "barrio": None,
            "direccion": None,
            "comercio_id": COMERCIO_ID,
            "estado_verificacion": "verificado",
            "activo": True,
        }

    async def insertar_promocion(*args: Any, **kwargs: Any) -> dict[str, Any]:
        eventos.append("insert")
        return {
            "id": uuid4(),
            "establecimiento_id": ESTABLECIMIENTO_ID,
            "producto_id": producto_id,
            "presentacion_id": None,
            "titulo": entrada.titulo,
            "tipo": "porcentaje",
            "porcentaje_descuento": 20,
            "precio_especial_cop": None,
            "pague_x": None,
            "lleve_y": None,
            "condiciones": entrada.condiciones,
            "vigente_desde": entrada.vigente_desde,
            "vigente_hasta": entrada.vigente_hasta,
            "hasta_revocar": False,
            "activa": True,
        }

    async def registrar_auditoria(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        servicio_modulo.repositorio, "bloquear_establecimiento", bloquear_establecimiento
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "obtener_establecimiento", obtener_establecimiento
    )
    monkeypatch.setattr(servicio_modulo.repositorio, "insertar_promocion", insertar_promocion)
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", registrar_auditoria)
    servicio = ServicioComercial(
        sesion=_SesionFalsa(),  # type: ignore[arg-type]
        puerto_cache=_CacheFalsa(),  # type: ignore[arg-type]
    )
    usuario = UsuarioAutenticado(
        id=COMERCIO_ID,
        email="comercio@armenia.co",
        rol="comercio",
        estado="activa",
    )

    await servicio.crear_promocion(ESTABLECIMIENTO_ID, entrada, usuario)

    assert eventos == ["lock", "autorizacion", "insert"]


def test_el_esquema_del_reclamo_sigue_siendo_estricto() -> None:
    """El contrato no relaja el telefono ni el mensaje al cerrar la carrera."""
    with pytest.raises(ValueError):
        ReclamoComercioEntrada(
            establecimiento_id=uuid4(),
            telefono_contacto="123",
            mensaje="Soy el dueno de la tienda y atiendo de 7 a 8.",
        )
