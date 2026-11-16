"""Adaptador HTTP hacia Open Food Facts con Circuit Breaker en memoria."""

from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any

import httpx

from app.dominio.unidades import parsear_cantidad
from app.puertos.catalogo_externo import ProductoExterno, PuertoCatalogoExterno

logger = logging.getLogger(__name__)


class AdaptadorOpenFoodFacts(PuertoCatalogoExterno):
    """Cliente HTTP hacia la API de Open Food Facts con tolerancia a fallos."""

    def __init__(
        self,
        user_agent: str = "ComparadorPreciosArmenia/1.0 (contacto@armenia.gov.co)",
        timeout_segundos: float = 3.0,
        max_reintentos: int = 2,
        umbral_fallos_circuito: int = 5,
        tiempo_recuperacion_circuito: float = 60.0,
        cliente_http: httpx.AsyncClient | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout_segundos
        self.max_reintentos = max_reintentos
        self.umbral_fallos = umbral_fallos_circuito
        self.tiempo_recuperacion = tiempo_recuperacion_circuito
        self._cliente = cliente_http

        # Estado del Circuit Breaker en memoria
        self.estado_circuito = "CLOSED"
        self.fallos_consecutivos = 0
        self.abierto_en = 0.0

    def puede_ejecutar(self, ahora: float | None = None) -> bool:
        """Determina si la peticion puede salir a la red segun el Circuit Breaker."""
        instante = ahora if ahora is not None else time.time()
        if self.estado_circuito == "OPEN":
            if instante - self.abierto_en >= self.tiempo_recuperacion:
                self.estado_circuito = "HALF_OPEN"
                return True
            return False
        return True

    def registrar_exito(self) -> None:
        """Reinicia el contador de fallos al recibir una respuesta exitosa."""
        self.fallos_consecutivos = 0
        self.estado_circuito = "CLOSED"

    def registrar_fallo(self, ahora: float | None = None) -> None:
        """Incrementa fallos y abre el circuito si supera el umbral configurado."""
        instante = ahora if ahora is not None else time.time()
        self.fallos_consecutivos += 1
        if self.fallos_consecutivos >= self.umbral_fallos or self.estado_circuito == "HALF_OPEN":
            self.estado_circuito = "OPEN"
            self.abierto_en = instante
            logger.warning(
                "Circuit Breaker Open Food Facts ABIERTO por 60s tras %d fallos.",
                self.fallos_consecutivos,
            )

    async def _realizar_peticion(self, url: str) -> dict[str, Any] | None:
        """Ejecuta la peticion con politica de reintentos controlada."""
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        intento = 0
        ultimo_error: Exception | None = None

        while intento <= self.max_reintentos:
            try:
                if self._cliente is not None:
                    resp = await self._cliente.get(url, headers=headers)
                else:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.get(url, headers=headers)

                if resp.status_code == 404:
                    self.registrar_exito()
                    return None

                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Error servidor {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )

                resp.raise_for_status()
                self.registrar_exito()
                return resp.json()  # type: ignore[no-any-return]

            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                ultimo_error = exc
                intento += 1
                if intento <= self.max_reintentos:
                    await asyncio.sleep(0.05 * intento)

        self.registrar_fallo()
        logger.error("Fallo definitivo consultando Open Food Facts: %s", ultimo_error)
        return None

    async def consultar_por_codigo_barras(self, codigo_barras: str) -> ProductoExterno | None:
        """Consulta Open Food Facts por codigo GTIN/EAN respetando el Circuit Breaker."""
        if not self.puede_ejecutar():
            logger.info("Peticion a Open Food Facts omitida: Circuit Breaker abierto.")
            return None

        url = f"https://world.openfoodfacts.org/api/v2/product/{codigo_barras}.json"
        datos = await self._realizar_peticion(url)
        if not datos or datos.get("status") != 1:
            return None

        p = datos.get("product", {})
        nombre = (
            p.get("product_name_es")
            or p.get("product_name")
            or p.get("generic_name_es")
            or p.get("generic_name")
        )
        if not nombre:
            return None

        marca = p.get("brands")
        imagen_url = p.get("image_url") or p.get("image_front_url")

        # Intentar extraer cantidad y unidad declarada
        cantidad_valor: Decimal | None = None
        unidad: str | None = None
        cant_texto = p.get("quantity")
        if cant_texto:
            cant_p = parsear_cantidad(str(cant_texto))
            if cant_p:
                cantidad_valor = cant_p.valor_cantidad
                unidad = cant_p.unidad

        return ProductoExterno(
            codigo_barras=codigo_barras,
            nombre=str(nombre).strip(),
            marca=str(marca).strip() if marca else None,
            cantidad_valor=cantidad_valor,
            unidad=unidad,
            imagen_url=str(imagen_url) if imagen_url else None,
        )
