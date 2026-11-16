"""Objeto inmutable de configuracion de parametros de negocio para el dominio puro."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParametrosDominio:
    """Parametros de calibracion del dominio puro sembrados desde config_parametro."""

    precio_min_cop: int = 50
    precio_max_cop: int = 2000000
    precio_ratio_extremo: float = 5.0
    observado_max_antiguedad_horas: int = 24
    vigencia_fresco_horas: float = 48.0
    vigencia_vida_media_horas: float = 72.0
    vigencia_vigente_dias: int = 7
    vigencia_antiguo_dias: int = 30
    vigencia_comercio_revalidar_dias: int = 30
    anomalia_ventana_dias: int = 14
    anomalia_n_min_referencia: int = 3
    anomalia_n_min_z: int = 5
    anomalia_z_umbral: float = 3.5
    anomalia_desviacion_pct_umbral: float = 0.30
    riesgo_pesos: dict[str, float] = field(
        default_factory=lambda: {
            "sin_foto": 0.15,
            "cuenta_nueva": 0.25,
            "rafaga": 0.40,
            "reputacion_baja": 0.20,
        }
    )
    riesgo_umbral_dudoso: float = 0.60
    cuenta_nueva_dias: int = 7
    cuenta_nueva_min_aceptados: int = 3
    reputacion_inicial: float = 0.500
    reputacion_baja_umbral: float = 0.350
    reputacion_corroboracion_tolerancia: float = 0.10
    rafaga_ventana_min: int = 30
    rafaga_min_cuentas: int = 3
    sello_n_min_validos: int = 3
    sello_min_fuentes: int = 2
    sello_dispersion_max: float = 0.15
    peso_con_foto: float = 1.2
    cache_ttl_segundos: int = 60
    cache_l1_segundos: int = 5
    limite_escrituras_ip_min: int = 20
    limite_reportes_hora_nuevo: int = 20
    limite_reportes_hora_normal: int = 60
    limite_reportes_dia: int = 200
    limite_fotos_hora_usuario: int = 30
    foto_max_kb: int = 300
    foto_tipos: list[str] = field(default_factory=lambda: ["image/webp", "image/jpeg"])

    @classmethod
    def desde_dict(cls, data: dict[str, Any]) -> ParametrosDominio:
        """Construye ParametrosDominio mapeando las claves con punto de config_parametro."""
        mapeo = {
            "precio.min_cop": "precio_min_cop",
            "precio.max_cop": "precio_max_cop",
            "precio.ratio_extremo": "precio_ratio_extremo",
            "observado.max_antiguedad_horas": "observado_max_antiguedad_horas",
            "vigencia.fresco_horas": "vigencia_fresco_horas",
            "vigencia.vida_media_horas": "vigencia_vida_media_horas",
            "vigencia.vigente_dias": "vigencia_vigente_dias",
            "vigencia.antiguo_dias": "vigencia_antiguo_dias",
            "anomalia.ventana_dias": "anomalia_ventana_dias",
            "anomalia.n_min_referencia": "anomalia_n_min_referencia",
            "anomalia.n_min_z": "anomalia_n_min_z",
            "anomalia.z_umbral": "anomalia_z_umbral",
            "anomalia.desviacion_pct_umbral": "anomalia_desviacion_pct_umbral",
            "riesgo.pesos": "riesgo_pesos",
            "riesgo.umbral_dudoso": "riesgo_umbral_dudoso",
            "cuenta_nueva.dias": "cuenta_nueva_dias",
            "cuenta_nueva.min_aceptados": "cuenta_nueva_min_aceptados",
            "reputacion.inicial": "reputacion_inicial",
            "reputacion.baja_umbral": "reputacion_baja_umbral",
            "sello.n_min_validos": "sello_n_min_validos",
            "sello.min_fuentes": "sello_min_fuentes",
            "sello.dispersion_max": "sello_dispersion_max",
            "peso.con_foto": "peso_con_foto",
            "rafaga.ventana_min": "rafaga_ventana_min",
            "rafaga.min_cuentas": "rafaga_min_cuentas",
            "limite.escrituras_ip_min": "limite_escrituras_ip_min",
            "limite.reportes_hora_nuevo": "limite_reportes_hora_nuevo",
            "limite.reportes_hora_normal": "limite_reportes_hora_normal",
            "limite.reportes_dia": "limite_reportes_dia",
            "limite.fotos_hora_usuario": "limite_fotos_hora_usuario",
            "foto.max_kb": "foto_max_kb",
            "foto.tipos": "foto_tipos",
        }
        kwargs: dict[str, Any] = {}
        for clave_sql, campo_python in mapeo.items():
            if clave_sql in data:
                kwargs[campo_python] = data[clave_sql]
        return cls(**kwargs)
