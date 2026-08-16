"""
Rotas de gestão de usuários do Clarity A.I.P.

⚠️ Protótipo: POST /usuarios está sem controle de acesso porque ainda não
existe conceito de admin/curador autenticado (Passo 4 introduz só o login).
Antes de qualquer uso além de demo local, restrinja este endpoint a um
papel administrativo.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import obter_usuario_com_tags
from app.models import Usuario
from app.schemas import UsuarioComTagsOut, UsuarioCriar

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/usuarios", tags=["usuarios"])


@router.post("", response_model=UsuarioComTagsOut, status_code=status.HTTP_201_CREATED)
async def criar_usuario(payload: UsuarioCriar, db: AsyncSession = Depends(get_db)) -> Usuario:
    """Cria um novo usuário (sem tags de acesso — atribuídas separadamente)."""
    usuario = Usuario(nome=payload.nome, email=payload.email)
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


@router.get("/{usuario_id}", response_model=UsuarioComTagsOut)
async def obter_usuario(usuario_id: int, db: AsyncSession = Depends(get_db)) -> Usuario:
    """Retorna um usuário e suas tags de acesso (permissões)."""
    usuario = await obter_usuario_com_tags(db, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return usuario
