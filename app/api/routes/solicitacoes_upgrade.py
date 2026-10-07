"""
Rotas de pedido de upgrade de tag do Clarity A.I.P.

Um usuário pede uma tag de acesso que ainda não tem (ex: "quero
Marketing3"). A aprovação (Fase 4 — admin/curadoria) reaproveita a mesma
regra de usuario_pode_curar: só aprova quem já tem, ele mesmo, a tag/nível
pedido — sem papel de "curador" separado.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.areas import AREAS_VALIDAS
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.security import extrair_area_nivel, usuario_pode_curar
from app.models import SolicitacaoUpgradeTag, TagSugestaoStatus, Usuario
from app.schemas import SolicitacaoUpgradeCriar, SolicitacaoUpgradeOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/solicitacoes-upgrade", tags=["solicitacoes-upgrade"])


@router.post("", response_model=SolicitacaoUpgradeOut, status_code=status.HTTP_201_CREATED)
async def solicitar_upgrade(
    payload: SolicitacaoUpgradeCriar,
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoUpgradeTag:
    area, nivel = extrair_area_nivel(payload.tag_solicitada)
    if not area or area not in AREAS_VALIDAS or not (1 <= nivel <= 4):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag inválida — formato 'Area+Nivel' com área em {AREAS_VALIDAS} e nível 1-4",
        )

    # usuario_pode_curar(usuario, tag) checa exatamente "o usuário já tem
    # tag/nível suficiente para essa área" — a mesma pergunta que "já tem
    # esse acesso?", só reaproveitada (ver app/core/security.py).
    if usuario_pode_curar(usuario, payload.tag_solicitada):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você já tem esse nível de acesso")

    stmt = select(SolicitacaoUpgradeTag).where(
        SolicitacaoUpgradeTag.usuario_id == usuario.id,
        SolicitacaoUpgradeTag.tag_solicitada == payload.tag_solicitada,
        SolicitacaoUpgradeTag.status == TagSugestaoStatus.PENDENTE_REVISAO,
    )
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Você já tem um pedido pendente para essa tag")

    solicitacao = SolicitacaoUpgradeTag(
        usuario_id=usuario.id,
        tag_solicitada=payload.tag_solicitada,
        justificativa=payload.justificativa,
    )
    db.add(solicitacao)
    await db.commit()
    await db.refresh(solicitacao)

    logger.info("Usuario %s solicitou upgrade para tag %s", usuario.id, payload.tag_solicitada)
    return solicitacao


@router.get("", response_model=list[SolicitacaoUpgradeOut])
async def listar_minhas_solicitacoes(
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SolicitacaoUpgradeTag]:
    """Histórico dos próprios pedidos de upgrade, mais recentes primeiro."""
    stmt = (
        select(SolicitacaoUpgradeTag)
        .where(SolicitacaoUpgradeTag.usuario_id == usuario.id)
        .order_by(SolicitacaoUpgradeTag.criada_em.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
