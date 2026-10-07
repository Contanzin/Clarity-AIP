"""Rotas de gestão de usuários do Clarity A.I.P."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import gerar_hash_senha, get_admin_user
from app.core.database import get_db
from app.core.security import obter_usuario_com_tags
from app.models import Usuario
from app.schemas import UsuarioComTagsOut, UsuarioCriar

logger = logging.getLogger(__name__)

SENHA_PADRAO = "12345"

router = APIRouter(prefix="/api/v1/usuarios", tags=["usuarios"])


@router.post(
    "", response_model=UsuarioComTagsOut, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_admin_user)],
)
async def criar_usuario(payload: UsuarioCriar, db: AsyncSession = Depends(get_db)) -> Usuario:
    """
    Cria um novo usuário (sem tags de acesso — atribuídas separadamente).

    A senha inicial é a senha padrão da empresa (ver SENHA_PADRAO) — o
    usuário troca pela própria em /perfil no primeiro acesso.
    """
    usuario = Usuario(nome=payload.nome, email=payload.email, senha_hash=gerar_hash_senha(SENHA_PADRAO))
    db.add(usuario)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário com esse email",
        )

    await db.refresh(usuario)
    return await obter_usuario_com_tags(db, usuario.id)


@router.get("/{usuario_id}", response_model=UsuarioComTagsOut, dependencies=[Depends(get_admin_user)])
async def obter_usuario(usuario_id: int, db: AsyncSession = Depends(get_db)) -> Usuario:
    """Retorna um usuário e suas tags de acesso (permissões)."""
    usuario = await obter_usuario_com_tags(db, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return usuario
