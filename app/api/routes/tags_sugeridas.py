"""
Rotas de curadoria de tags sugeridas do Clarity A.I.P (Passo 6).

Um curador revisa a sugestão da IA e aprova (com ou sem correção) ou
rejeita antes do documento ficar acessível. Elegibilidade de curadoria
reaproveita o RBAC existente (app/core/security.py:usuario_pode_curar):
só pode aprovar/corrigir uma tag quem já tem, ele mesmo, uma tag de área e
nível suficientes — ninguém libera acesso a algo que não pode ver.

Cada sugestão é revisada individualmente por id — não existe endpoint de
aprovação em lote (decisão deliberada, ver docs/README).
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.areas import AREAS_VALIDAS
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.security import extrair_area_nivel, tag_precisa_atencao, usuario_pode_curar
from app.models import DocumentoStatus, TagSugerida, TagSugestaoStatus, Usuario
from app.schemas import (
    AprovarTagRequest,
    DocumentoResumoOut,
    RejeitarTagRequest,
    TagSugeridaDetalheOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tags-sugeridas", tags=["tags-sugeridas"])


def _to_detalhe(tag_sugerida: TagSugerida) -> TagSugeridaDetalheOut:
    return TagSugeridaDetalheOut(
        id=tag_sugerida.id,
        tag_sugerida=tag_sugerida.tag_sugerida,
        justificativa=tag_sugerida.justificativa,
        confianca=tag_sugerida.confianca,
        status=tag_sugerida.status,
        precisa_atencao=tag_precisa_atencao(tag_sugerida.confianca),
        revisor_id=tag_sugerida.revisor_id,
        revisada_em=tag_sugerida.revisada_em,
        comentario_revisor=tag_sugerida.comentario_revisor,
        documento=DocumentoResumoOut(
            id=tag_sugerida.documento.id,
            titulo=tag_sugerida.documento.titulo,
            status=tag_sugerida.documento.status,
        ),
    )


async def _obter_tag_sugerida(db: AsyncSession, tag_id: int) -> TagSugerida:
    stmt = (
        select(TagSugerida)
        .where(TagSugerida.id == tag_id)
        .options(selectinload(TagSugerida.documento))
    )
    result = await db.execute(stmt)
    tag_sugerida = result.scalar_one_or_none()
    if tag_sugerida is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sugestão não encontrada")
    return tag_sugerida


def _exigir_pendente(tag_sugerida: TagSugerida) -> None:
    if tag_sugerida.status != TagSugestaoStatus.PENDENTE_REVISAO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sugestão já foi revisada (status atual: {tag_sugerida.status.value})",
        )


@router.get("", response_model=list[TagSugeridaDetalheOut])
async def listar_pendentes(
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TagSugeridaDetalheOut]:
    """
    Lista sugestões pendentes de revisão que ESTE usuário tem clearance para
    curar — não mostra a fila inteira, só o que ele já teria acesso a ver.
    """
    stmt = (
        select(TagSugerida)
        .where(TagSugerida.status == TagSugestaoStatus.PENDENTE_REVISAO)
        .options(selectinload(TagSugerida.documento))
    )
    result = await db.execute(stmt)
    sugestoes = result.scalars().all()

    visiveis = [s for s in sugestoes if usuario_pode_curar(usuario, s.tag_sugerida)]
    return [_to_detalhe(s) for s in visiveis]


@router.get("/{tag_id}", response_model=TagSugeridaDetalheOut)
async def obter_sugestao(
    tag_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TagSugeridaDetalheOut:
    """Abertura individual de uma sugestão — base para a tela de revisão do Passo 9."""
    tag_sugerida = await _obter_tag_sugerida(db, tag_id)
    if not usuario_pode_curar(usuario, tag_sugerida.tag_sugerida):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem clearance para revisar esta sugestão")
    return _to_detalhe(tag_sugerida)


@router.post("/{tag_id}/aprovar", response_model=TagSugeridaDetalheOut)
async def aprovar(
    tag_id: int,
    payload: AprovarTagRequest,
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TagSugeridaDetalheOut:
    """
    Aprova a sugestão, opcionalmente corrigindo área/nível. O documento
    passa a 'aprovado' com a área/nível FINAL decidido aqui (a sugestão
    original da IA é preservada em tag_sugerida.tag_sugerida para auditoria).
    """
    tag_sugerida = await _obter_tag_sugerida(db, tag_id)
    _exigir_pendente(tag_sugerida)

    area_sugerida, nivel_sugerido = extrair_area_nivel(tag_sugerida.tag_sugerida)
    area_final = payload.area or area_sugerida
    nivel_final = payload.nivel if payload.nivel is not None else nivel_sugerido

    if area_final not in AREAS_VALIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Área '{area_final}' fora da lista permitida: {AREAS_VALIDAS}",
        )

    if not usuario_pode_curar(usuario, f"{area_final}{nivel_final}"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem a tag necessária para aprovar este nível de acesso",
        )

    tag_sugerida.status = TagSugestaoStatus.APROVADA
    tag_sugerida.revisada_em = datetime.now(timezone.utc)
    tag_sugerida.revisor_id = usuario.id
    tag_sugerida.comentario_revisor = payload.comentario

    documento = tag_sugerida.documento
    documento.area = area_final
    documento.nivel_acesso_exigido = nivel_final
    documento.status = DocumentoStatus.APROVADO

    await db.commit()
    await db.refresh(tag_sugerida)
    await db.refresh(documento)

    logger.info(
        "Documento %s aprovado por usuario %s como %s%s (sugestao original: %s)",
        documento.id, usuario.id, area_final, nivel_final, tag_sugerida.tag_sugerida,
    )
    return _to_detalhe(tag_sugerida)


@router.post("/{tag_id}/rejeitar", response_model=TagSugeridaDetalheOut)
async def rejeitar(
    tag_id: int,
    payload: RejeitarTagRequest,
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TagSugeridaDetalheOut:
    """Rejeita a sugestão — o documento permanece 'pendente' (fail-safe: nunca fica acessível)."""
    tag_sugerida = await _obter_tag_sugerida(db, tag_id)
    _exigir_pendente(tag_sugerida)

    if not usuario_pode_curar(usuario, tag_sugerida.tag_sugerida):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem a tag necessária para revisar esta sugestão",
        )

    tag_sugerida.status = TagSugestaoStatus.REJEITADA
    tag_sugerida.revisada_em = datetime.now(timezone.utc)
    tag_sugerida.revisor_id = usuario.id
    tag_sugerida.comentario_revisor = payload.comentario

    await db.commit()
    await db.refresh(tag_sugerida)

    logger.info("Sugestão %s rejeitada por usuario %s: %s", tag_id, usuario.id, payload.comentario)
    return _to_detalhe(tag_sugerida)
