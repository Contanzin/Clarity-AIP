"""
Rotas de administração do Clarity A.I.P (Fase 4).

Tudo aqui exige get_admin_user (usuario.is_admin=True) — diferente das
rotas de curadoria (app/api/routes/tags_sugeridas.py), que usam
usuario_pode_curar (só aprova quem já tem a tag). O admin é "master": pode
conceder/revogar qualquer tag e aprovar qualquer pedido de upgrade, mesmo
sem ter ele mesmo aquele acesso — por isso fica isolado num papel próprio
(is_admin) em vez de reaproveitar o RBAC de curadoria.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.areas import AREAS_VALIDAS
from app.core.auth import get_admin_user
from app.core.database import get_db
from app.core.security import extrair_area_nivel, obter_usuario_com_tags
from app.models import Documento, SolicitacaoUpgradeTag, TagSugestaoStatus, Usuario, UsuarioTag
from app.schemas import (
    AdminAprovarSolicitacaoRequest,
    AdminRejeitarSolicitacaoRequest,
    AdminTagCriar,
    AdminUsuarioAtualizar,
    DocumentoAdminOut,
    SolicitacaoUpgradeAdminOut,
    UsuarioComTagsOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(get_admin_user)])


# ============================================================================
# USUÁRIOS E TAGS
# ============================================================================

@router.get("/usuarios", response_model=list[UsuarioComTagsOut])
async def listar_usuarios(db: AsyncSession = Depends(get_db)) -> list[Usuario]:
    stmt = select(Usuario).order_by(Usuario.nome)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _obter_usuario(db: AsyncSession, usuario_id: int) -> Usuario:
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return usuario


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioComTagsOut)
async def atualizar_usuario(
    usuario_id: int,
    payload: AdminUsuarioAtualizar,
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    usuario = await _obter_usuario(db, usuario_id)

    if payload.departamento is not None and payload.departamento not in AREAS_VALIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Departamento '{payload.departamento}' fora da lista permitida: {AREAS_VALIDAS}",
        )

    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(usuario, campo, valor)

    await db.commit()
    return await obter_usuario_com_tags(db, usuario.id)


@router.post("/usuarios/{usuario_id}/tags", response_model=UsuarioComTagsOut, status_code=status.HTTP_201_CREATED)
async def conceder_tag(
    usuario_id: int,
    payload: AdminTagCriar,
    admin: Usuario = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    usuario = await _obter_usuario(db, usuario_id)

    area, nivel = extrair_area_nivel(payload.tag)
    if not area or area not in AREAS_VALIDAS or not (1 <= nivel <= 4):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag inválida — formato 'Area+Nivel' com área em {AREAS_VALIDAS} e nível 1-4",
        )

    db.add(UsuarioTag(
        usuario_id=usuario.id,
        tag=payload.tag,
        atribuida_por_usuario_id=admin.id,
        observacoes=payload.observacoes,
    ))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuário já tem essa tag")

    return await obter_usuario_com_tags(db, usuario.id)


@router.delete("/usuarios/{usuario_id}/tags/{tag}", response_model=UsuarioComTagsOut)
async def revogar_tag(
    usuario_id: int,
    tag: str,
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    usuario = await _obter_usuario(db, usuario_id)

    stmt = select(UsuarioTag).where(UsuarioTag.usuario_id == usuario_id, UsuarioTag.tag == tag)
    usuario_tag = (await db.execute(stmt)).scalar_one_or_none()
    if usuario_tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não tem essa tag")

    await db.delete(usuario_tag)
    await db.commit()
    return await obter_usuario_com_tags(db, usuario.id)


# ============================================================================
# DOCUMENTOS (todos, independente de status)
# ============================================================================

@router.get("/documentos", response_model=list[DocumentoAdminOut])
async def listar_todos_documentos(db: AsyncSession = Depends(get_db)) -> list[DocumentoAdminOut]:
    stmt = (
        select(Documento)
        .options(selectinload(Documento.usuario_criador))
        .order_by(Documento.data_criacao.desc())
    )
    result = await db.execute(stmt)
    documentos = result.scalars().all()
    return [
        DocumentoAdminOut(
            id=d.id,
            titulo=d.titulo,
            area=d.area,
            nivel_acesso_exigido=d.nivel_acesso_exigido,
            status=d.status,
            data_criacao=d.data_criacao,
            usuario_criador_nome=d.usuario_criador.nome if d.usuario_criador else None,
        )
        for d in documentos
    ]


@router.delete("/documentos/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_documento(documento_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Exclui um documento e seus logs/sugestão associados (via cascade)."""
    documento = await db.get(Documento, documento_id)
    if documento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    await db.delete(documento)
    await db.commit()

    logger.info("Documento %s excluído", documento_id)


# ============================================================================
# FILA DE PEDIDOS DE UPGRADE DE TAG
# ============================================================================

def _to_admin_out(s: SolicitacaoUpgradeTag) -> SolicitacaoUpgradeAdminOut:
    return SolicitacaoUpgradeAdminOut(
        id=s.id,
        tag_solicitada=s.tag_solicitada,
        justificativa=s.justificativa,
        status=s.status,
        criada_em=s.criada_em,
        revisada_em=s.revisada_em,
        comentario_revisor=s.comentario_revisor,
        usuario_id=s.usuario_id,
        usuario_nome=s.usuario.nome,
        usuario_email=s.usuario.email,
    )


async def _obter_solicitacao(db: AsyncSession, solicitacao_id: int) -> SolicitacaoUpgradeTag:
    stmt = (
        select(SolicitacaoUpgradeTag)
        .where(SolicitacaoUpgradeTag.id == solicitacao_id)
        .options(selectinload(SolicitacaoUpgradeTag.usuario))
    )
    solicitacao = (await db.execute(stmt)).scalar_one_or_none()
    if solicitacao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return solicitacao


@router.get("/solicitacoes-upgrade", response_model=list[SolicitacaoUpgradeAdminOut])
async def listar_solicitacoes(db: AsyncSession = Depends(get_db)) -> list[SolicitacaoUpgradeAdminOut]:
    stmt = (
        select(SolicitacaoUpgradeTag)
        .options(selectinload(SolicitacaoUpgradeTag.usuario))
        .order_by(SolicitacaoUpgradeTag.criada_em.desc())
    )
    result = await db.execute(stmt)
    return [_to_admin_out(s) for s in result.scalars().all()]


@router.post("/solicitacoes-upgrade/{solicitacao_id}/aprovar", response_model=SolicitacaoUpgradeAdminOut)
async def aprovar_solicitacao(
    solicitacao_id: int,
    payload: AdminAprovarSolicitacaoRequest,
    admin: Usuario = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoUpgradeAdminOut:
    solicitacao = await _obter_solicitacao(db, solicitacao_id)
    if solicitacao.status != TagSugestaoStatus.PENDENTE_REVISAO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pedido já foi revisado")

    stmt = select(UsuarioTag).where(
        UsuarioTag.usuario_id == solicitacao.usuario_id,
        UsuarioTag.tag == solicitacao.tag_solicitada,
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        db.add(UsuarioTag(
            usuario_id=solicitacao.usuario_id,
            tag=solicitacao.tag_solicitada,
            atribuida_por_usuario_id=admin.id,
            observacoes="Concedida via pedido de upgrade de tag",
        ))

    solicitacao.status = TagSugestaoStatus.APROVADA
    solicitacao.revisada_em = datetime.now(timezone.utc)
    solicitacao.revisor_id = admin.id
    solicitacao.comentario_revisor = payload.comentario

    await db.commit()
    await db.refresh(solicitacao)
    logger.info("Admin %s aprovou pedido de upgrade %s (usuario %s, tag %s)",
                admin.id, solicitacao_id, solicitacao.usuario_id, solicitacao.tag_solicitada)
    return _to_admin_out(solicitacao)


@router.post("/solicitacoes-upgrade/{solicitacao_id}/rejeitar", response_model=SolicitacaoUpgradeAdminOut)
async def rejeitar_solicitacao(
    solicitacao_id: int,
    payload: AdminRejeitarSolicitacaoRequest,
    admin: Usuario = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoUpgradeAdminOut:
    solicitacao = await _obter_solicitacao(db, solicitacao_id)
    if solicitacao.status != TagSugestaoStatus.PENDENTE_REVISAO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pedido já foi revisado")

    solicitacao.status = TagSugestaoStatus.REJEITADA
    solicitacao.revisada_em = datetime.now(timezone.utc)
    solicitacao.revisor_id = admin.id
    solicitacao.comentario_revisor = payload.comentario

    await db.commit()
    await db.refresh(solicitacao)
    logger.info("Admin %s rejeitou pedido de upgrade %s: %s", admin.id, solicitacao_id, payload.comentario)
    return _to_admin_out(solicitacao)
