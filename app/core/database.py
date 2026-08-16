"""
Configuração do SQLAlchemy e banco de dados.

Define o engine, session factory e utilities para trabalhar com o banco.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Base para todos os modelos ORM (inherit daqui)
Base = declarative_base()

# Engine assíncrono do SQLAlchemy
# Usa asyncpg como driver (não-bloqueante, perfetto para FastAPI)
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Log de SQL em development
    future=True,
    pool_size=10,
    max_overflow=20,
)

# Factory para criar sessões
# AsyncSession garante que queries não bloqueiam a event loop
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """
    Dependency injection para FastAPI endpoints.
    
    Uso em endpoints:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            result = await db.execute(...)
    
    A sessão é automaticamente fechada após o endpoint retornar.
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Cria todas as tabelas (se não existirem).
    
    Nota: As tabelas já foram criadas pelo SQL puro em db/01_init_schema.sql.
    Esta função é mais para fallback ou testes locais.
    
    Uso no main.py:
        @app.on_event("startup")
        async def startup():
            await init_db()
    """
    async with engine.begin() as conn:
        # Cria as tabelas definidas em Base.metadata
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created or already exist")


async def close_db():
    """
    Fecha o engine (limpeza ao desligar a app).
    
    Uso no main.py:
        @app.on_event("shutdown")
        async def shutdown():
            await close_db()
    """
    await engine.dispose()
    logger.info("Database engine disposed")
