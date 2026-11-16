"""Servicio de aplicacion para la gestion de los 43 parametros de negocio (T-36)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.auditoria import registrar_auditoria
from app.compartido.errores import ValidacionError
from app.compartido.parametros import invalidar_cache_parametros
from app.compartido.seguridad import UsuarioAutenticado
from app.modulos.moderacion.esquemas_casos import (
    ActualizarParametrosEntrada,
    ListaParametrosRespuesta,
    ParametroItem,
)

RANGO_ENTERO_2_A_10 = "Entero 2..10"

# Definicion de especificaciones de los 43 parametros de la Seccion 2.4
ESPECIFICACIONES: dict[str, tuple[str, str, str]] = {
    "precio.min_cop": ("int", "Entero 10..1000", "Precio mínimo aceptado en COP"),
    "precio.max_cop": ("int", "Entero 100000..10000000", "Precio máximo aceptado en COP"),
    "precio.ratio_extremo": (
        "float",
        "Número 2.0..20.0",
        "Multiplicador/divisor para ratio_extremo",
    ),
    "observado.max_antiguedad_horas": (
        "int",
        "Entero 1..168",
        "Horas máximas hacia atrás en observado_en",
    ),
    "vigencia.fresco_horas": ("int", "Entero 6..168", "Horas con factor temporal 1.0"),
    "vigencia.vida_media_horas": ("int", "Entero 12..336", "Horas de vida media exponencial"),
    "vigencia.vigente_dias": (
        "int",
        "Entero 1..30",
        "Días máximos para considerar vigente un reporte",
    ),
    "vigencia.antiguo_dias": (
        "int",
        "Entero 8..90",
        "Días máximos para mostrar reporte desactualizado",
    ),
    "vigencia.comercio_revalidar_dias": (
        "int",
        "Entero 7..90",
        "Días sin cambios para revalidar comercio",
    ),
    "anomalia.ventana_dias": (
        "int",
        "Entero 3..60",
        "Días de antigüedad máxima de conjunto de referencia",
    ),
    "anomalia.n_min_referencia": (
        "int",
        RANGO_ENTERO_2_A_10,
        "Mínimo de reportes para usar referencia",
    ),
    "anomalia.n_min_z": ("int", "Entero 4..20", "Mínimo de reportes para usar z-score modificado"),
    "anomalia.z_umbral": ("float", "Número 2.0..6.0", "Umbral absoluto del z-score modificado"),
    "anomalia.desviacion_pct_umbral": (
        "float",
        "Número 0.10..0.80",
        "Umbral de desviación porcentual",
    ),
    "riesgo.pesos": ("dict", "Objeto JSON con suma 1.0", "Pesos de las 4 señales de contexto"),
    "riesgo.umbral_dudoso": ("float", "Número 0.30..0.95", "Puntaje de riesgo para marcar dudoso"),
    "cuenta_nueva.dias": ("int", "Entero 1..30", "Días para considerar cuenta como nueva"),
    "cuenta_nueva.min_aceptados": (
        "int",
        "Entero 1..20",
        "Reportes corroborados para dejar de ser nueva",
    ),
    "reputacion.inicial": ("float", "Número 0.300..0.700", "Reputación inicial de perfil nuevo"),
    "reputacion.baja_umbral": (
        "float",
        "Número 0.100..0.490",
        "Umbral para señal de reputacion_baja",
    ),
    "reputacion.corroboracion_tolerancia": (
        "float",
        "Número 0.03..0.25",
        "Tolerancia para corroboración",
    ),
    "rafaga.ventana_min": ("int", "Entero 5..120", "Ventana en minutos para ráfaga por huella_red"),
    "rafaga.min_cuentas": ("int", RANGO_ENTERO_2_A_10, "Cuentas mínimas para declarar ráfaga"),
    "sello.n_min_validos": (
        "int",
        RANGO_ENTERO_2_A_10,
        "Mínimo de reportes vigentes para sello confiable",
    ),
    "sello.min_fuentes": ("int", "Entero 2..5", "Mínimo de fuentes distintas para sello confiable"),
    "sello.dispersion_max": (
        "float",
        "Número 0.05..0.40",
        "Dispersión máxima MAD/mediana para confiable",
    ),
    "peso.con_foto": ("float", "Número 1.0..2.0", "Multiplicador de peso con fotografía"),
    "cache.ttl_segundos": ("int", "Entero 10..60", "TTL máximo en caché de comparación (EC-02)"),
    "cache.l1_segundos": ("int", "Entero 1..15", "TTL en caché L1 de memoria"),
    "limite.reportes_hora_nuevo": ("int", "Entero 5..100", "Máximo reportes/h cuenta nueva"),
    "limite.reportes_hora_normal": (
        "int",
        "Entero 20..300",
        "Máximo reportes/h cuenta establecida",
    ),
    "limite.reportes_dia": ("int", "Entero 50..1000", "Máximo reportes/día por usuario"),
    "limite.consultas_ip_min": ("int", "Entero 30..600", "Máximo lecturas/min por IP"),
    "limite.escrituras_ip_min": ("int", "Entero 5..100", "Máximo escrituras/min por IP"),
    "limite.correcciones_ip_dia": ("int", "Entero 1..20", "Máximo correcciones/día por IP"),
    "limite.fotos_hora_usuario": ("int", "Entero 5..120", "Máximo fotos/h por usuario"),
    "foto.max_kb": ("int", "Entero 100..1024", "Tamaño máximo foto en KB"),
    "foto.tipos": ("list", "Arreglo no vacío", "MIME types aceptados para fotos"),
    "huella.retencion_dias": ("int", "Entero 7..90", "Días retención huella_red"),
    "comparacion.radio_km": ("float", "Número 1.0..50.0", "Radio km para filtrar por cercanía"),
    "comparacion.max_resultados": ("int", "Entero 10..100", "Máximo resultados devueltos"),
    "disputa.min_reportes_y_cuentas": (
        "dict",
        "JSON con enteros >= 2",
        "Mínimo reportes y cuentas disputa",
    ),
    "disputa.ventana_y_diferencia": (
        "dict",
        "JSON ventana y diferencia",
        "Ventana y diferencia para disputa",
    ),
}


def validar_parametro(clave: str, valor: Any) -> Any:
    if clave not in ESPECIFICACIONES:
        raise ValidacionError(f"Parametro no reconocido: '{clave}'")
    tipo, rango, _ = ESPECIFICACIONES[clave]
    if tipo == "int":
        if not isinstance(valor, int) or isinstance(valor, bool):
            raise ValidacionError(f"El valor de '{clave}' debe ser un entero ({rango})")
        _validar_rango_int(clave, valor)
    elif tipo == "float":
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            raise ValidacionError(f"El valor de '{clave}' debe ser numérico ({rango})")
        _validar_rango_float(clave, float(valor))
    elif tipo == "dict":
        _validar_dict(clave, valor)
    elif tipo == "list" and (not isinstance(valor, list) or len(valor) == 0):
        raise ValidacionError(f"El valor de '{clave}' debe ser una lista no vacía")
    return valor


def _validar_rango_int(k: str, v: int) -> None:
    rangos: dict[str, tuple[int, int]] = {
        "precio.min_cop": (10, 1000),
        "precio.max_cop": (100000, 10000000),
        "observado.max_antiguedad_horas": (1, 168),
        "vigencia.fresco_horas": (6, 168),
        "vigencia.vida_media_horas": (12, 336),
        "vigencia.vigente_dias": (1, 30),
        "vigencia.antiguo_dias": (8, 90),
        "vigencia.comercio_revalidar_dias": (7, 90),
        "anomalia.ventana_dias": (3, 60),
        "anomalia.n_min_referencia": (2, 10),
        "anomalia.n_min_z": (4, 20),
        "cuenta_nueva.dias": (1, 30),
        "cuenta_nueva.min_aceptados": (1, 20),
        "rafaga.ventana_min": (5, 120),
        "rafaga.min_cuentas": (2, 10),
        "sello.n_min_validos": (2, 10),
        "sello.min_fuentes": (2, 5),
        "cache.ttl_segundos": (10, 60),
        "cache.l1_segundos": (1, 15),
        "limite.reportes_hora_nuevo": (5, 100),
        "limite.reportes_hora_normal": (20, 300),
        "limite.reportes_dia": (50, 1000),
        "limite.consultas_ip_min": (30, 600),
        "limite.escrituras_ip_min": (5, 100),
        "limite.correcciones_ip_dia": (1, 20),
        "limite.fotos_hora_usuario": (5, 120),
        "foto.max_kb": (100, 1024),
        "huella.retencion_dias": (7, 90),
        "comparacion.max_resultados": (10, 100),
    }
    if k in rangos and not (rangos[k][0] <= v <= rangos[k][1]):
        raise ValidacionError(f"'{k}' ({v}) fuera de rango [{rangos[k][0]}..{rangos[k][1]}]")


def _validar_rango_float(k: str, v: float) -> None:
    rangos: dict[str, tuple[float, float]] = {
        "precio.ratio_extremo": (2.0, 20.0),
        "anomalia.z_umbral": (2.0, 6.0),
        "anomalia.desviacion_pct_umbral": (0.10, 0.80),
        "riesgo.umbral_dudoso": (0.30, 0.95),
        "reputacion.inicial": (0.300, 0.700),
        "reputacion.baja_umbral": (0.100, 0.490),
        "reputacion.corroboracion_tolerancia": (0.03, 0.25),
        "sello.dispersion_max": (0.05, 0.40),
        "peso.con_foto": (1.0, 2.0),
        "comparacion.radio_km": (1.0, 50.0),
    }
    if k in rangos and not (rangos[k][0] <= v <= rangos[k][1]):
        raise ValidacionError(f"'{k}' ({v}) fuera de rango [{rangos[k][0]}..{rangos[k][1]}]")


def _validar_dict(k: str, v: Any) -> None:
    if not isinstance(v, dict):
        raise ValidacionError(f"El valor de '{k}' debe ser un diccionario JSON")
    if k == "riesgo.pesos":
        esperadas = {"sin_foto", "cuenta_nueva", "rafaga", "reputacion_baja"}
        if set(v.keys()) != esperadas:
            raise ValidacionError(f"'{k}' requiere exactamente las claves {esperadas}")
        suma = sum(float(x) for x in v.values())
        if abs(suma - 1.0) > 1e-4:
            raise ValidacionError(
                f"Los pesos en '{k}' deben sumar exactamente 1.0 (suma actual: {suma})"
            )


class ServicioParametros:
    def __init__(self, sesion: AsyncSession) -> None:
        self.sesion = sesion

    async def listar_parametros(self) -> ListaParametrosRespuesta:
        sql = text("""
            SELECT clave, valor, descripcion, actualizado_en
            FROM public.config_parametro
            ORDER BY clave ASC;
        """)
        filas = (await self.sesion.execute(sql)).fetchall()
        items: list[ParametroItem] = []
        for f in filas:
            clave = str(f.clave)
            tipo, rango, desc_def = ESPECIFICACIONES.get(
                clave, ("any", "Cualquiera", f.descripcion or "")
            )
            items.append(
                ParametroItem(
                    clave=clave,
                    valor=f.valor,
                    descripcion=f.descripcion or desc_def,
                    tipo=tipo,
                    rango_valido=rango,
                    actualizado_en=f.actualizado_en,
                )
            )
        return ListaParametrosRespuesta(datos=items)

    async def actualizar_parametros(
        self, entrada: ActualizarParametrosEntrada, moderador: UsuarioAutenticado
    ) -> ListaParametrosRespuesta:
        if not entrada.parametros:
            raise ValidacionError("Debe proporcionar al menos un parámetro para actualizar")
        for k, v in entrada.parametros.items():
            validar_parametro(k, v)

        claves = list(entrada.parametros.keys())
        sql_ant = text(
            "SELECT clave, valor FROM public.config_parametro WHERE clave = ANY(:claves);"
        )
        anteriores = {
            f.clave: f.valor
            for f in (await self.sesion.execute(sql_ant, {"claves": claves})).fetchall()
        }

        for k, v in entrada.parametros.items():
            sql_upd = text("""
                UPDATE public.config_parametro
                SET valor = CAST(:val AS jsonb), actualizado_en = now()
                WHERE clave = :clave;
            """)
            await self.sesion.execute(sql_upd, {"clave": k, "val": json.dumps(v)})

        await registrar_auditoria(
            self.sesion,
            actor_id=moderador.id,
            rol=moderador.rol,
            accion="actualizar_parametros",
            entidad="config_parametro",
            entidad_id=",".join(claves),
            antes=anteriores,
            despues=entrada.parametros,
        )
        await self.sesion.flush()
        invalidar_cache_parametros()
        return await self.listar_parametros()
