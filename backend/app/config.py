"""Configuracion de la aplicacion backend mediante variables de entorno."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Any, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Configuracion(BaseSettings):
    """Esquema tipado para variables de entorno de la aplicacion."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Servidor y Entorno
    ENTORNO: str = "local"
    FASTAPI_HOST: str = "127.0.0.1"
    FASTAPI_PORT: int = 8000
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://comparador-precios-rho.vercel.app",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parsear_cors_origins(cls, valor: Any) -> list[str]:
        """Acepta lista JSON o cadena separada por comas en variables de entorno."""
        if isinstance(valor, str):
            texto = valor.strip()
            if not texto:
                return []
            if texto.startswith("["):
                cargado = json.loads(texto)
                return [str(o).strip().rstrip("/") for o in cargado if str(o).strip()]
            return [o.strip().rstrip("/") for o in texto.split(",") if o.strip()]
        if isinstance(valor, list):
            return [str(o).strip().rstrip("/") for o in valor if str(o).strip()]
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://comparador-precios-rho.vercel.app",
        ]

    # Supabase (API, Auth, Storage)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWKS_URL: str = ""

    # Base de Datos y Cache
    DATABASE_URL: str = ""
    MIGRATIONS_DATABASE_URL: str = ""
    REDIS_URL: str = ""

    # Seguridad Operativa y Privacidad (Ley 1581)
    HUELLA_SECRETO_MAESTRO: str = "secreto_maestro_hmac_desarrollo_local_32b"
    JOB_TOKEN: str = "token_interno_jobs_desarrollo_local"  # noqa: S105

    # Contacto Legal y Servicios Externos
    CONTACTO_LEGAL_EMAIL: str = "contacto@cue.edu.co"
    OFF_USER_AGENT: str = "ComparadorPreciosArmenia/1.0"
    GEMINI_API_KEY: str = ""

    @model_validator(mode="after")
    def derivar_jwks_url(self) -> Self:
        """Deriva automaticamente SUPABASE_JWKS_URL si no esta explicitamente configurada."""
        if not self.SUPABASE_JWKS_URL and self.SUPABASE_URL:
            url_base = self.SUPABASE_URL.rstrip("/")
            self.SUPABASE_JWKS_URL = f"{url_base}/auth/v1/.well-known/jwks.json"
        return self


@lru_cache(maxsize=1)
def obtener_configuracion() -> Configuracion:
    """Retorna una instancia cacheada de la configuracion de la aplicacion."""
    return Configuracion()
