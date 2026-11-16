"""Pruebas de integracion para flujo completo de moderacion, sanciones y auditoria (T-33)."""

from __future__ import annotations

from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.config import obtener_configuracion
from app.main import app


def generar_token(usuario_id: str, email: str = "mod@armenia.gov.co") -> str:
    cfg = obtener_configuracion()
    secreto = cfg.SUPABASE_JWT_SECRET or "secreto_jwt_prueba_local_32_bytes_min"
    cfg.SUPABASE_JWT_SECRET = secreto
    return jwt.encode({"sub": usuario_id, "email": email}, secreto, algorithm="HS256")


async def crear_perfil(uid: str, rol: str, reputacion: float = 0.5) -> None:
    async with sesion_transaccional() as sesion:
        sql = text("""
            INSERT INTO perfil (id, alias, rol, estado, reputacion)
            VALUES (:id, :alias, CAST(:rol AS rol_usuario), 'activa', :rep)
            ON CONFLICT (id) DO UPDATE SET
                rol = CAST(:rol AS rol_usuario),
                estado = 'activa',
                reputacion = :rep;
        """)
        await sesion.execute(
            sql, {"id": uid, "alias": f"u_{uid[:8]}", "rol": rol, "rep": reputacion}
        )


async def setup_reporte_y_caso(reportante_id: str) -> tuple[str, str, str, str]:
    async with sesion_transaccional() as sesion:
        p_id = (
            await sesion.execute(text("SELECT id FROM producto WHERE activo = true LIMIT 1;"))
        ).scalar_one()
        pr_id = (
            await sesion.execute(
                text(
                    "SELECT id FROM presentacion WHERE producto_id = :p AND activa = true LIMIT 1;"
                ),
                {"p": p_id},
            )
        ).scalar_one()
        e_id = (
            await sesion.execute(
                text("SELECT id FROM establecimiento WHERE activo = true LIMIT 1;")
            )
        ).scalar_one()

        sql_rep = text("""
            INSERT INTO reporte_precio (
                producto_id, presentacion_id, establecimiento_id, reportante_id,
                precio_cop, precio_por_base, cantidad_base_snapshot, fuente,
                estado, estado_original, conjunto_referencia, observado_en
            ) VALUES (
                :p, :pr, :e, :u, 5000, 5.0, 1000, 'usuario',
                'dudoso', 'dudoso', 'sin_referencia', now()
            ) RETURNING id;
        """)
        r_id = (
            await sesion.execute(sql_rep, {"p": p_id, "pr": pr_id, "e": e_id, "u": reportante_id})
        ).scalar_one()

        sql_caso = text("""
            INSERT INTO caso_moderacion (
                tipo, referencia_tabla, referencia_id, detalle, prioridad, estado
            ) VALUES (
                'reporte_dudoso', 'reporte_precio', :rid, '{"motivo":"prueba"}'::jsonb, 2, 'abierto'
            ) RETURNING id;
        """)
        c_id = (await sesion.execute(sql_caso, {"rid": r_id})).scalar_one()
        return str(c_id), str(r_id), str(pr_id), str(e_id)


@pytest.mark.asyncio
async def test_listar_y_obtener_caso() -> None:
    mod_id = str(uuid4())
    rep_id = str(uuid4())
    await crear_perfil(mod_id, "moderador")
    await crear_perfil(rep_id, "reportante")
    caso_id, _, _, _ = await setup_reporte_y_caso(rep_id)
    token = generar_token(mod_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        res = await cliente.get(
            "/v1/moderacion/casos?estado=abierto&limite=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        datos = res.json()
        assert datos["total"] >= 1
        casos_visibles = list(datos["datos"])
        for off in range(100, datos["total"], 100):
            if any(c["id"] == caso_id for c in casos_visibles):
                break
            sig = await cliente.get(
                f"/v1/moderacion/casos?estado=abierto&limite=100&offset={off}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert sig.status_code == 200
            casos_visibles.extend(sig.json()["datos"])
        assert any(c["id"] == caso_id for c in casos_visibles)

        res_det = await cliente.get(
            f"/v1/moderacion/casos/{caso_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert res_det.status_code == 200
        det = res_det.json()
        assert det["id"] == caso_id
        assert det["referencia_datos"] is not None


@pytest.mark.asyncio
async def test_resolver_caso_descartar() -> None:
    mod_id = str(uuid4())
    rep_id = str(uuid4())
    await crear_perfil(mod_id, "moderador")
    await crear_perfil(rep_id, "reportante")
    caso_id, reporte_id, _, _ = await setup_reporte_y_caso(rep_id)
    token = generar_token(mod_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        res = await cliente.post(
            f"/v1/moderacion/casos/{caso_id}/resolver",
            headers={"Authorization": f"Bearer {token}"},
            json={"decision": "descartar", "nota": "Reporte es perfectamente valido"},
        )
        assert res.status_code == 200
        assert res.json()["decision"] == "descartar"

    async with sesion_transaccional() as sesion:
        estado_rep = (
            await sesion.execute(
                text("SELECT estado::text FROM reporte_precio WHERE id = :id;"), {"id": reporte_id}
            )
        ).scalar_one()
        assert estado_rep == "aceptado"


@pytest.mark.asyncio
async def test_resolver_caso_confirmar_penaliza_reputacion() -> None:
    mod_id = str(uuid4())
    rep_id = str(uuid4())
    await crear_perfil(mod_id, "moderador")
    await crear_perfil(rep_id, "reportante", reputacion=0.5)
    caso_id, reporte_id, _, _ = await setup_reporte_y_caso(rep_id)
    token = generar_token(mod_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        res = await cliente.post(
            f"/v1/moderacion/casos/{caso_id}/resolver",
            headers={"Authorization": f"Bearer {token}"},
            json={"decision": "confirmar", "nota": "Precio falso intencional"},
        )
        assert res.status_code == 200
        assert res.json()["decision"] == "confirmar"

    async with sesion_transaccional() as sesion:
        estado_rep = (
            await sesion.execute(
                text("SELECT estado::text FROM reporte_precio WHERE id = :id;"), {"id": reporte_id}
            )
        ).scalar_one()
        assert estado_rep == "rechazado"
        fila_perf = (
            await sesion.execute(
                text("SELECT reportes_malos_confirmados, reputacion FROM perfil WHERE id = :id;"),
                {"id": rep_id},
            )
        ).first()
        assert fila_perf.reportes_malos_confirmados >= 1
        assert float(fila_perf.reputacion) < 0.5


@pytest.mark.asyncio
async def test_resolver_caso_sancionar_y_apelacion() -> None:
    mod_id = str(uuid4())
    rep_id = str(uuid4())
    await crear_perfil(mod_id, "moderador")
    await crear_perfil(rep_id, "reportante")
    caso_id, _, _, _ = await setup_reporte_y_caso(rep_id)
    token_mod = generar_token(mod_id)
    token_user = generar_token(rep_id, "rep@armenia.gov.co")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        res = await cliente.post(
            f"/v1/moderacion/casos/{caso_id}/resolver",
            headers={"Authorization": f"Bearer {token_mod}"},
            json={
                "decision": "sancionar",
                "nota": "Conducta abusiva reiterada",
                "sancion": {"tipo": "suspension", "motivo": "Spam continuo", "dias_suspension": 5},
            },
        )
        assert res.status_code == 200

        res_usr = await cliente.get(
            f"/v1/moderacion/usuarios/{rep_id}", headers={"Authorization": f"Bearer {token_mod}"}
        )
        assert res_usr.status_code == 200
        usr_datos = res_usr.json()
        assert usr_datos["estado"] == "suspendida"
        assert len(usr_datos["sanciones"]) >= 1
        sancion_id = usr_datos["sanciones"][0]["id"]

        # Apelar como el usuario sancionado
        res_ap = await cliente.post(
            f"/v1/moderacion/sanciones/{sancion_id}/apelacion",
            headers={"Authorization": f"Bearer {token_user}"},
            json={"apelacion": "Pido disculpas, fue un error de digitacion de mi teclado."},
        )
        assert res_ap.status_code == 200

        # Resolver apelacion aprobando
        res_res = await cliente.post(
            f"/v1/moderacion/sanciones/{sancion_id}/resolver-apelacion",
            headers={"Authorization": f"Bearer {token_mod}"},
            json={"aprobar": True, "nota": "Apelacion aceptada por primera vez"},
        )
        assert res_res.status_code == 200

        res_usr2 = await cliente.get(
            f"/v1/moderacion/usuarios/{rep_id}", headers={"Authorization": f"Bearer {token_mod}"}
        )
        assert res_usr2.json()["estado"] == "activa"

        # Comprobar bitacora de auditoria
        res_aud = await cliente.get(
            "/v1/moderacion/auditoria?entidad=sancion",
            headers={"Authorization": f"Bearer {token_mod}"},
        )
        assert res_aud.status_code == 200
        assert res_aud.json()["total"] >= 1
