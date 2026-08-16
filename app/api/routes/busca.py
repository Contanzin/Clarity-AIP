"""
Rota de busca do Clarity A.I.P (Passo 7 — o core do produto).

Fluxo: pergunta em linguagem natural → embedding → busca vetorial. Duas
consultas são feitas, com propósitos diferentes:

1. Busca "de verdade" (_buscar_melhor_acessivel): vetorial, só entre
   documentos aprovados que o usuário JÁ tem permissão de acessar (filtro
   pelas tags dele). Só o resultado desta consulta pode virar título,
   resumo ou link na resposta.
2. Checagem de existência (_buscar_melhor_global), usada SÓ quando (1) não
   encontra nada relevante: vetorial entre TODOS os documentos aprovados,
   mas retornando apenas metadados (área, nível, distância) — nunca
   título, resumo ou qualquer conteúdo. Serve só para responder "existe
   algo relevante, mas está restrito", sem revelar do que se trata.

Isso preserva o princípio do projeto (ver README.md): a IA nunca gera
conteúdo a partir de um documento que o usuário não pode ver — ela só
pode, na pior das hipóteses, saber que "algo" existe e qual tag falta.

Toda consulta (encontrada, restrita ou não encontrada) é registrada em
logs_acesso (Passo 8 — auditoria).
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.gemini import gerar_embedding, gerar_resumo_executivo
from app.core.security import extrair_area_nivel, registrar_acesso
from app.models import AcessoResultado, Documento, DocumentoStatus, Usuario
from app.schemas import BuscaRequest, BuscaResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/busca", tags=["busca"])

# Distância de cosseno acima da qual consideramos "não relevante o
# suficiente" (0 = idêntico, 2 = oposto). Calibrado empiricamente: com
# gemini-embedding-001, perguntas de fato relacionadas ao acervo de teste
# ficaram na faixa 0.18-0.24, e perguntas sem relação nenhuma (ex: "qual a
# capital da Mongólia?") ficaram em 0.50+ — 0.4 dá margem para paráfrases
# sem deixar passar perguntas realmente não relacionadas. Pode exigir
# reajuste com um acervo maior e mais variado.
DISTANCIA_MAXIMA_RELEVANTE = 0.4

BASE_DIR = Path(__file__).resolve().parents[3]


@router.post("", response_model=BuscaResponse)
async def buscar(
    payload: BuscaRequest,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuscaResponse:
    ip_request = request.client.host if request.client else None
    embedding_pergunta = await gerar_embedding(payload.pergunta)

    documento_id = await _buscar_melhor_acessivel(db, usuario, embedding_pergunta)

    if documento_id is not None:
        documento = await db.get(Documento, documento_id)

        if not documento.resumo_executivo:
            texto = _ler_conteudo(documento.caminho_arquivo)
            documento.resumo_executivo = await gerar_resumo_executivo(texto)
            await db.commit()
            await db.refresh(documento)

        await registrar_acesso(
            db, usuario.id, documento.id, AcessoResultado.PERMITIDO,
            ip_request=ip_request, query_texto=payload.pergunta,
        )
        return BuscaResponse(
            resultado="encontrado",
            mensagem="Documento encontrado.",
            documento_id=documento.id,
            titulo=documento.titulo,
            link=f"/api/v1/documentos/{documento.id}/arquivo",
            resumo_executivo=documento.resumo_executivo,
        )

    melhor_global = await _buscar_melhor_global(db, embedding_pergunta)

    if melhor_global is None:
        await registrar_acesso(
            db, usuario.id, None, AcessoResultado.ACESSO_NEGADO,
            motivo_negacao="documento_nao_encontrado",
            ip_request=ip_request, query_texto=payload.pergunta,
        )
        return BuscaResponse(
            resultado="nao_encontrado",
            mensagem="Nenhum documento relevante foi encontrado para essa pergunta.",
        )

    documento_id_restrito, area, nivel = melhor_global
    await registrar_acesso(
        db, usuario.id, documento_id_restrito, AcessoResultado.ACESSO_NEGADO,
        motivo_negacao="tag_insuficiente",
        ip_request=ip_request, query_texto=payload.pergunta,
    )
    return BuscaResponse(
        resultado="restrito",
        mensagem="Existe um documento relevante para essa pergunta, mas o acesso é restrito.",
        tag_necessaria=f"{area}{nivel}",
    )


async def _buscar_melhor_acessivel(
    db: AsyncSession, usuario: Usuario, embedding_pergunta: list[float]
) -> Optional[int]:
    """Melhor match entre documentos aprovados que o usuário já pode acessar."""
    condicoes_acesso = [
        and_(Documento.area == area, Documento.nivel_acesso_exigido <= nivel)
        for area, nivel in (extrair_area_nivel(t.tag) for t in usuario.tags)
        if area
    ]
    if not condicoes_acesso:
        return None

    stmt = (
        select(Documento.id, Documento.embedding.cosine_distance(embedding_pergunta).label("distancia"))
        .where(
            Documento.status == DocumentoStatus.APROVADO,
            Documento.embedding.is_not(None),
            or_(*condicoes_acesso),
        )
        .order_by("distancia")
        .limit(1)
    )
    result = await db.execute(stmt)
    linha = result.first()
    if linha is None or linha.distancia > DISTANCIA_MAXIMA_RELEVANTE:
        return None
    return linha.id


async def _buscar_melhor_global(db: AsyncSession, embedding_pergunta: list[float]):
    """
    Melhor match entre TODOS os documentos aprovados, indiferente de
    permissão — só metadados (nunca título/resumo/conteúdo). Usado apenas
    quando _buscar_melhor_acessivel não encontrou nada, para informar
    "existe algo relevante, mas restrito" sem revelar do que se trata.
    """
    stmt = (
        select(Documento.id, Documento.area, Documento.nivel_acesso_exigido,
               Documento.embedding.cosine_distance(embedding_pergunta).label("distancia"))
        .where(Documento.status == DocumentoStatus.APROVADO, Documento.embedding.is_not(None))
        .order_by("distancia")
        .limit(1)
    )
    result = await db.execute(stmt)
    linha = result.first()
    if linha is None or linha.distancia > DISTANCIA_MAXIMA_RELEVANTE:
        return None
    return linha.id, linha.area, linha.nivel_acesso_exigido


def _ler_conteudo(caminho_relativo: str) -> str:
    return (BASE_DIR / caminho_relativo).read_text(encoding="utf-8")
