"""
Aplicação principal do Clarity A.I.P.

FastAPI app com integração de banco de dados, modelos ORM, e rotas básicas.
"""

import logging
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import auth as auth_routes
from app.api.routes import busca as busca_routes
from app.api.routes import documentos as documentos_routes
from app.api.routes import paginas as paginas_routes
from app.api.routes import tags_sugeridas as tags_sugeridas_routes
from app.api.routes import usuarios as usuarios_routes
from app.config import settings
from app.core.database import get_db, init_db, close_db

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar app FastAPI
BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(
    title="Clarity A.I.P",
    version="0.1.0",
    description="Knowledge Broker com controle de acesso para Claro",
    debug=settings.debug,
)

# Montar diretórios estáticos
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Configurar Jinja2 templates
app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Sessão de login via cookie assinado (ver app/core/auth.py)
# https_only=False porque o protótipo roda em http://localhost; habilitar em produção.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=not settings.debug,
)


# ============================================================================
# EVENT HANDLERS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Executado ao iniciar a aplicação.
    
    Inicializa conexão com banco e cria tabelas (se necessário).
    """
    logger.info("🚀 Iniciando Clarity A.I.P...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug: {settings.debug}")
    logger.info(f"Database: {settings.database_url}")
    
    # Inicializar banco (criar tabelas se não existirem)
    await init_db()
    
    logger.info("✅ Clarity A.I.P iniciado com sucesso!")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Executado ao desligar a aplicação.
    
    Fecha conexões com o banco de dados.
    """
    logger.info("🛑 Desligando Clarity A.I.P...")
    await close_db()
    logger.info("✅ Desligamento concluído!")


# ============================================================================
# ROTAS / ENDPOINTS
# ============================================================================

@app.get("/health")
async def healthcheck() -> dict:
    """
    Health check simples para verificar se a app está rodando.
    
    Returns:
        {"status": "ok", "service": "clarity_aip"}
    """
    return {
        "status": "ok",
        "service": "clarity_aip",
        "environment": settings.app_env,
    }


@app.get("/api/v1/debug/db-info")
async def debug_db_info(db: AsyncSession = Depends(get_db)) -> dict:
    """
    [DEBUG] Retorna informações sobre a conexão com o banco.
    
    Apenas disponível em development.
    """
    if not settings.debug:
        return {"error": "Debug endpoint not available in production"}
    
    return {
        "database_url": settings.database_url.replace(settings.postgres_password, "***"),
        "host": settings.postgres_host,
        "port": settings.postgres_port,
        "database": settings.postgres_db,
        "user": settings.postgres_user,
    }


# ============================================================================
# ROTAS
# ============================================================================

app.include_router(auth_routes.router)
app.include_router(usuarios_routes.router)
app.include_router(documentos_routes.router)
app.include_router(tags_sugeridas_routes.router)
app.include_router(busca_routes.router)
app.include_router(paginas_routes.router)
