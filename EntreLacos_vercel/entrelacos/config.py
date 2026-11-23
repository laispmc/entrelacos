"""Configurações da aplicação EntreLaços.

Valores sensíveis vêm de variáveis de ambiente (arquivo .env localmente,
painel "Environment Variables" na Vercel).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _url_banco():
    """Postgres em produção (DATABASE_URL); SQLite local como padrão.

    Na Vercel o disco é somente leitura, então sem DATABASE_URL o SQLite vai
    para /tmp (funciona, mas os dados somem quando a função reinicia).
    """
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if url:
        # O SQLAlchemy precisa saber qual driver usar (psycopg 3)
        for prefixo in ("postgres://", "postgresql://"):
            if url.startswith(prefixo):
                return "postgresql+psycopg://" + url[len(prefixo):]
        return url
    if os.environ.get("VERCEL"):
        return "sqlite:////tmp/entrelacos.db"
    return f"sqlite:///{BASE_DIR / 'instance' / 'entrelacos.db'}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _url_banco()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    MAX_IMAGE_SIZE = 3 * 1024 * 1024      # 3 MB por imagem de capa
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # limite da requisição (a Vercel aceita até 4,5 MB)
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "chave-apenas-para-testes"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True


config_por_nome = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
