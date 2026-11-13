"""Pruebas de integracion para derechos ARCO Ley 1581, cuentas y fotos (T-22 y T-27)."""

from __future__ import annotations

from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.config import obtener_configuracion
from app.main import app


def generar_token(usuario_id: str) -> str:
    """Genera token JWT firmado con el secreto simetrico de prueba."""
    cfg = obtener_configuracion()
    secreto = cfg.SUPABASE_JWT_SECRET or "secreto_jwt_prueba_local_32_bytes_min"
    cfg.SUPABASE_JWT_SECRET = secreto
    payload = {"sub": usuario_id, "email": f"{usuario_id[:8]}@ejemplo.com"}
    return jwt.encode(payload, secreto, algorithm="HS256")


@pytest.mark.asyncio
async def test_consultar_politica_tratamiento_publica() -> None:
    """Verifica que la politica de datos sea publica y exponga version 1.0 y correo ARCO."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.get("/v1/legal/politica-tratamiento")
        assert resp.status_code == 200
        datos = resp.json()
        assert datos["version"] == "1.0"
        assert len(datos["finalidades"]) >= 1
        assert "@" in datos["contacto_legal_email"]


@pytest.mark.asyncio
async def test_mi_cuenta_sin_autorizacion_devuelve_403() -> None:
    """Verifica que un usuario autenticado sin consentimiento reciba 403 AUTORIZACION_REQUERIDA."""
    usuario_id = str(uuid4())
    token = generar_token(usuario_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.get("/v1/mi-cuenta", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        cuerpo = resp.json()
        assert cuerpo["codigo"] == "AUTORIZACION_REQUERIDA"


@pytest.mark.asyncio
async def test_registrar_autorizacion_y_consultar_perfil() -> None:
    """Verifica el registro de autorizacion previa Ley 1581 y posterior consulta de perfil."""
    usuario_id = str(uuid4())
    token = generar_token(usuario_id)
    alias = f"arco_{usuario_id[:8]}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp_post = await cliente.post(
            "/v1/mi-cuenta/autorizacion",
            headers={"Authorization": f"Bearer {token}"},
            json={"alias": alias, "version_politica": "1.0", "acepta": True},
        )
        assert resp_post.status_code == 201
        datos_post = resp_post.json()
        assert datos_post["alias"] == alias
        assert datos_post["version_politica"] == "1.0"

        resp_get = await cliente.get(
            "/v1/mi-cuenta",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_get.status_code == 200
        datos_get = resp_get.json()
        assert datos_get["alias"] == alias
        assert datos_get["estado"] == "activa"
        assert datos_get["autorizacion_vigente"]["version_politica"] == "1.0"


@pytest.mark.asyncio
async def test_actualizar_alias_y_control_de_duplicados() -> None:
    """Verifica la actualizacion de alias publico y el rechazo 409 ante alias ya tomados."""
    uid1 = str(uuid4())
    uid2 = str(uuid4())
    token1 = generar_token(uid1)
    token2 = generar_token(uid2)
    alias1 = f"alias_{uid1[:8]}"
    alias2 = f"alias_{uid2[:8]}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        await cliente.post(
            "/v1/mi-cuenta/autorizacion",
            headers={"Authorization": f"Bearer {token1}"},
            json={"alias": alias1, "version_politica": "1.0", "acepta": True},
        )
        await cliente.post(
            "/v1/mi-cuenta/autorizacion",
            headers={"Authorization": f"Bearer {token2}"},
            json={"alias": alias2, "version_politica": "1.0", "acepta": True},
        )

        resp_conflicto = await cliente.patch(
            "/v1/mi-cuenta",
            headers={"Authorization": f"Bearer {token2}"},
            json={"alias": alias1},
        )
        assert resp_conflicto.status_code == 409

        nuevo_alias = f"nuevo_{uid2[:8]}"
        resp_ok = await cliente.patch(
            "/v1/mi-cuenta",
            headers={"Authorization": f"Bearer {token2}"},
            json={"alias": nuevo_alias},
        )
        assert resp_ok.status_code == 200
        assert resp_ok.json()["alias"] == nuevo_alias


@pytest.mark.asyncio
async def test_fotos_url_subida_flujo_completo() -> None:
    """Verifica generacion de URL firmada, rechazo sin consentimiento y por tamano excedido."""
    uid = str(uuid4())
    token = generar_token(uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # 1. Sin consentimiento -> 403
        resp_sin = await cliente.post(
            "/v1/fotos/url-subida",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "test.webp", "tipo_mime": "image/webp", "tamano_bytes": 1000},
        )
        assert resp_sin.status_code == 403

        # Dar consentimiento
        await cliente.post(
            "/v1/mi-cuenta/autorizacion",
            headers={"Authorization": f"Bearer {token}"},
            json={"alias": f"f_{uid[:8]}", "version_politica": "1.0", "acepta": True},
        )

        # 2. Tamano excedido (> 300 KB) -> 422
        resp_grande = await cliente.post(
            "/v1/fotos/url-subida",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "nombre_archivo": "a.webp",
                "tipo_mime": "image/webp",
                "tamano_bytes": 400 * 1024,
            },
        )
        assert resp_grande.status_code == 422

        # 3. Solicitud valida -> 201 Created
        resp_ok = await cliente.post(
            "/v1/fotos/url-subida",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "e.webp", "tipo_mime": "image/webp", "tamano_bytes": 120000},
        )
        assert resp_ok.status_code == 201
        datos = resp_ok.json()
        assert uid in datos["ruta"]
        assert datos["ruta"].endswith(".webp")
        assert "http" in datos["url_firmada"]
        assert datos["expira_en"] == 300


@pytest.mark.asyncio
async def test_eliminar_cuenta_anonimizacion_arco() -> None:
    """Verifica que DELETE /v1/mi-cuenta anonimice reportes, revoque datos y asiente auditoria."""
    uid = str(uuid4())
    token = generar_token(uid)
    alias = f"sup_{uid[:8]}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        await cliente.post(
            "/v1/mi-cuenta/autorizacion",
            headers={"Authorization": f"Bearer {token}"},
            json={"alias": alias, "version_politica": "1.0", "acepta": True},
        )

        async with sesion_transaccional() as sesion:
            res_pres = (
                await sesion.execute(text("SELECT id, producto_id FROM presentacion LIMIT 1;"))
            ).first()
            res_est = (
                await sesion.execute(text("SELECT id FROM establecimiento LIMIT 1;"))
            ).first()
            assert res_pres is not None
            assert res_est is not None
            pres_id, prod_id = res_pres[0], res_pres[1]
            est_id = res_est[0]

            sql_rep = text("""
                INSERT INTO reporte_precio (
                    producto_id, presentacion_id, establecimiento_id, precio_cop,
                    cantidad_base_snapshot, precio_por_base, observado_en,
                    estado, estado_original, fuente, conjunto_referencia,
                    reportante_id, foto_prueba_path
                ) VALUES (
                    :prod_id, :pres_id, :est_id, 3500,
                    1.000, 3500.000000, now(),
                    'aceptado', 'aceptado', 'usuario', 'sin_referencia',
                    :uid, 'fotos/2026/11/prueba.webp'
                );
            """)
            await sesion.execute(
                sql_rep,
                {"prod_id": prod_id, "pres_id": pres_id, "est_id": est_id, "uid": uid},
            )

        resp_del = await cliente.delete(
            "/v1/mi-cuenta", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp_del.status_code == 200
        assert resp_del.json()["estado"] == "eliminada"

        async with sesion_transaccional() as sesion:
            res_rep = (
                await sesion.execute(
                    text("""
                    SELECT reportante_id, foto_prueba_path
                    FROM reporte_precio
                    WHERE presentacion_id = :pres_id AND establecimiento_id = :est_id
                    ORDER BY creado_en DESC LIMIT 1;
                """),
                    {"pres_id": pres_id, "est_id": est_id},
                )
            ).fetchone()
            assert res_rep is not None
            assert res_rep[0] is None
            assert res_rep[1] is None

            res_perf = (
                await sesion.execute(
                    text("SELECT alias, estado FROM perfil WHERE id = :uid;"),
                    {"uid": uid},
                )
            ).fetchone()
            assert res_perf is not None
            assert res_perf[0].startswith("eliminado_")
            assert res_perf[1] == "eliminada"

            res_aut = (
                await sesion.execute(
                    text("SELECT revocada_en FROM autorizacion_datos WHERE usuario_id = :uid;"),
                    {"uid": uid},
                )
            ).fetchone()
            assert res_aut is not None
            assert res_aut[0] is not None
