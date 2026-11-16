"""Pruebas de integración para la migración 0002 (Catálogo, Establecimientos y 43 Parámetros)."""

import pytest
from sqlalchemy import text

from app.bd import sesion_transaccional

CLAVES_43_ESPERADAS = {
    "precio.min_cop",
    "precio.max_cop",
    "precio.ratio_extremo",
    "observado.max_antiguedad_horas",
    "vigencia.fresco_horas",
    "vigencia.vida_media_horas",
    "vigencia.vigente_dias",
    "vigencia.antiguo_dias",
    "vigencia.comercio_revalidar_dias",
    "anomalia.ventana_dias",
    "anomalia.n_min_referencia",
    "anomalia.n_min_z",
    "anomalia.z_umbral",
    "anomalia.desviacion_pct_umbral",
    "riesgo.pesos",
    "riesgo.umbral_dudoso",
    "cuenta_nueva.dias",
    "cuenta_nueva.min_aceptados",
    "reputacion.inicial",
    "reputacion.baja_umbral",
    "reputacion.corroboracion_tolerancia",
    "rafaga.ventana_min",
    "rafaga.min_cuentas",
    "sello.n_min_validos",
    "sello.min_fuentes",
    "sello.dispersion_max",
    "peso.con_foto",
    "cache.ttl_segundos",
    "cache.l1_segundos",
    "limite.reportes_hora_nuevo",
    "limite.reportes_hora_normal",
    "limite.reportes_dia",
    "limite.consultas_ip_min",
    "limite.escrituras_ip_min",
    "limite.correcciones_ip_dia",
    "limite.fotos_hora_usuario",
    "foto.max_kb",
    "foto.tipos",
    "huella.retencion_dias",
    "comparacion.radio_km",
    "comparacion.max_resultados",
    "disputa.min_reportes_y_cuentas",
    "disputa.ventana_y_diferencia",
}


@pytest.mark.asyncio
async def test_tablas_catalogo_y_establecimientos_existen() -> None:
    """Verifica que las tablas del catálogo y establecimientos existan en public."""
    async with sesion_transaccional() as sesion:
        query = text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                  'categoria', 'producto', 'presentacion',
                  'alias_producto', 'establecimiento', 'config_parametro'
              );
        """)
        resultado = await sesion.execute(query)
        tablas = {fila[0] for fila in resultado.fetchall()}
        esperadas = {
            "categoria",
            "producto",
            "presentacion",
            "alias_producto",
            "establecimiento",
            "config_parametro",
        }
        assert esperadas.issubset(tablas)


@pytest.mark.asyncio
async def test_categorias_base_insertadas() -> None:
    """Verifica que existan exactamente las 10 categorías base con IDs 1 a 10."""
    async with sesion_transaccional() as sesion:
        resultado = await sesion.execute(text("SELECT id, nombre FROM categoria ORDER BY id ASC;"))
        categorias = resultado.fetchall()
        assert len(categorias) >= 10
        ids = [cat[0] for cat in categorias]
        assert set(range(1, 11)).issubset(set(ids))


@pytest.mark.asyncio
async def test_exactamente_43_parametros_en_config_parametro() -> None:
    """Verifica que config_parametro contenga exactamente las 43 claves de negocio."""
    async with sesion_transaccional() as sesion:
        resultado = await sesion.execute(text("SELECT clave FROM config_parametro;"))
        claves_en_bd = {fila[0] for fila in resultado.fetchall()}
        assert CLAVES_43_ESPERADAS.issubset(claves_en_bd)
        assert len(CLAVES_43_ESPERADAS) == 43


@pytest.mark.asyncio
async def test_app_backend_puede_leer_config_parametro() -> None:
    """Verifica que bajo SET LOCAL ROLE app_backend; se pueda consultar config_parametro."""
    async with sesion_transaccional() as sesion:
        # sesion_transaccional ejecuta automáticamente SET LOCAL ROLE app_backend;
        resultado = await sesion.execute(
            text("SELECT valor FROM config_parametro WHERE clave = 'precio.min_cop';")
        )
        fila = resultado.fetchone()
        assert fila is not None
        assert fila[0] == 50
