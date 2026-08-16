"""
Rotas de autenticação do Clarity A.I.P.

Login simplificado (só email, sem senha) — ver app/core/auth.py para a
justificativa e o ponto de extensão para um provedor real (AD/SSO).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthProvider,
    encerrar_sessao,
    get_auth_provider,
    get_current_user,
    iniciar_sessao,
)
from app.core.database import get_db
from app.models import Usuario
from app.schemas import LoginRequest, UsuarioComTagsOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=UsuarioComTagsOut)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_provider: AuthProvider = Depends(get_auth_provider),
) -> Usuario:
    """
    Autentica pelo email e abre uma sessão.

    Resposta genérica em caso de falha (não revela se o email existe, se
    está inativo, etc.) para não vazar informação sobre a base de usuários.
    """
    usuario = await auth_provider.autenticar(db, payload.email)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    iniciar_sessao(request, usuario)
    return usuario


@router.post("/logout")
async def logout(request: Request) -> dict:
    """Encerra a sessão atual."""
    encerrar_sessao(request)
    return {"status": "ok"}


@router.get("/me", response_model=UsuarioComTagsOut)
async def me(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    """Retorna o usuário autenticado e suas tags de acesso (permissões)."""
    return usuario
