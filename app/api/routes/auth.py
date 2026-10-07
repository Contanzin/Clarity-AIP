"""Rotas de autenticação do Clarity A.I.P."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthProvider,
    encerrar_sessao,
    gerar_hash_senha,
    get_auth_provider,
    get_current_user,
    iniciar_sessao,
    verificar_senha,
)
from app.core.database import get_db
from app.models import Usuario
from app.schemas import LoginRequest, TrocarSenhaRequest, UsuarioComTagsOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=UsuarioComTagsOut)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_provider: AuthProvider = Depends(get_auth_provider),
) -> Usuario:
    """
    Autentica por email + senha e abre uma sessão.

    Resposta genérica em caso de falha (não revela se o email existe, se
    está inativo, ou se só a senha estava errada) para não vazar informação
    sobre a base de usuários.
    """
    usuario = await auth_provider.autenticar(db, payload.email, payload.senha)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
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


@router.post("/senha")
async def trocar_senha(
    payload: TrocarSenhaRequest,
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Troca a senha do usuário autenticado — exige a senha atual correta."""
    if not verificar_senha(payload.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Senha atual incorreta")

    usuario.senha_hash = gerar_hash_senha(payload.senha_nova)
    await db.commit()
    return {"status": "ok"}
