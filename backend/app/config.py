"""Configuracion de la aplicacion backend mediante variables de entorno."""

from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

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
