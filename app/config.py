"""
Configuração centralizada da aplicação Clarity A.I.P.

Carrega variáveis de ambiente e disponibiliza settings globais.
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Settings da aplicação.
    
    Todas as variáveis são carregadas do arquivo .env via pydantic.
    Padrão: variáveis de ambiente > valores default.
    """

    # === APP ===
    app_name: str = "Clarity A.I.P"
    app_env: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", 8000))

    # === DATABASE ===
    # Nota: asyncpg é o driver assíncrono para PostgreSQL
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://clarity_user:clarity_password@localhost:5432/clarity_aip"
    )
    # Se DATABASE_URL não estiver definida, pode-se construir a partir de componentes
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", 5432))
    postgres_db: str = os.getenv("POSTGRES_DB", "clarity_aip")
    postgres_user: str = os.getenv("POSTGRES_USER", "clarity_user")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "clarity_password")

    # === GEMINI API ===
    # ⚠️ AVISO DE PRIVACIDADE:
    # O free tier do Gemini pode usar dados de requisição para melhorar o modelo.
    # Nunca use dados reais da Claro sem um plano pago com garantias de privacidade!
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    # Alias mantido pela Google apontando pro modelo flash-lite atual
    # recomendado — evita fixar uma versão que pode ser retirada (já
    # aconteceu com gemini-1.5-flash). "lite" porque, no free tier, o
    # gemini-flash-latest "cheio" mostrou instabilidade de disponibilidade
    # (503 "high demand") durante o desenvolvimento deste passo — para uma
    # tarefa de classificação simples como esta, flash-lite é suficiente e
    # pareceu mais estável. Ver app/core/gemini.py.
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
    enable_gemini_privacy_notice: bool = os.getenv("ENABLE_GEMINI_PRIVACY_NOTICE", "True").lower() == "true"

    # === SEGURANÇA ===
    session_secret: str = os.getenv("SESSION_SECRET", "change-me-in-production")

    # === APLICAÇÃO ===
    # Dimensão do embedding (padrão: Gemini usa 768)
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", 768))

    # Mínima confiança para sugestão de tag não ser destacada (< 0.7 = atenção extra)
    min_confidence_no_warning: float = float(os.getenv("MIN_CONFIDENCE_NO_WARNING", 0.7))

    class Config:
        env_file = ".env"
        case_sensitive = False
        # Ignora variáveis do .env que não são usadas pela app (ex: as de
        # setup do banco em db/setup.ps1, como POSTGRES_SUPERUSER*).
        extra = "ignore"


# Instância global de settings (importar como `from app.config import settings`)
settings = Settings()
