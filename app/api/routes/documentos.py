"""
Rotas de ingestão de documentos do Clarity A.I.P.

Passo 5: recebe um documento (texto colado ou upload .txt), gera o
embedding e uma sugestão de tag via Gemini, e cria o Documento com
status='pendente'. A aprovação humana da sugestão (Passo 6) ainda não
existe — até lá, o documento fica sempre inacessível (fail-safe: nunca
aprovado automaticamente pela IA).
"""

import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.gemini import (
    GeminiIndisponivelError,
    GeminiNaoConfiguradoError,
    gerar_embedding,
    sugerir_tag,
)
from app.core.security import registrar_acesso, tag_precisa_atencao, validar_acesso
from app.models import AcessoResultado, Documento, DocumentoStatus, TagSugerida, TagSugestaoStatus, Usuario
from app.schemas import DocumentoOut, TagSugeridaOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documentos", tags=["documentos"])

# clarity_aip/app/api/routes/documentos.py -> clarity_aip/uploads
UPLOADS_DIR = Path(__file__).resolve().parents[3] / "uploads"
TAMANHO_MAXIMO_BYTES = 2 * 1024 * 1024  # 2 MB — suficiente para texto, evita abuso


@router.post("", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED)
async def ingerir_documento(
    titulo: str = Form(..., min_length=1, max_length=500),
    conteudo: Optional[str] = Form(None),
    arquivo: Optional[UploadFile] = File(None),
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentoOut:
    texto = await _extrair_texto(conteudo, arquivo)

    # Só grava em disco depois que a IA responder com sucesso, para não
    # deixar arquivo órfão em uploads/ se a chamada ao Gemini falhar.
    try:
        embedding = await gerar_embedding(texto)
        sugestao = await sugerir_tag(texto)
    except GeminiNaoConfiguradoError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except (GeminiIndisponivelError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    caminho_arquivo = _salvar_texto(titulo, texto)

    documento = Documento(
        titulo=titulo,
        # area/nivel começam com o valor sugerido pela IA — o documento
        # continua 'pendente' (inacessível) até um curador confirmar ou
        # corrigir isso no Passo 6.
        area=sugestao.area,
        nivel_acesso_exigido=sugestao.nivel,
        status=DocumentoStatus.PENDENTE,
        caminho_arquivo=str(caminho_arquivo),
        embedding=embedding,
        usuario_criador_id=usuario.id,
    )
    db.add(documento)
    await db.flush()  # popula documento.id sem commitar ainda

    tag_sugerida = TagSugerida(
        documento_id=documento.id,
        tag_sugerida=f"{sugestao.area}{sugestao.nivel}",
        justificativa=sugestao.justificativa,
        confianca=sugestao.confianca,
        status=TagSugestaoStatus.PENDENTE_REVISAO,
    )
    db.add(tag_sugerida)
    await db.commit()
    await db.refresh(documento)
    await db.refresh(tag_sugerida)

    return DocumentoOut(
        id=documento.id,
        titulo=documento.titulo,
        area=documento.area,
        nivel_acesso_exigido=documento.nivel_acesso_exigido,
        status=documento.status,
        caminho_arquivo=documento.caminho_arquivo,
        data_criacao=documento.data_criacao,
        tag_sugerida=TagSugeridaOut(
            id=tag_sugerida.id,
            tag_sugerida=tag_sugerida.tag_sugerida,
            justificativa=tag_sugerida.justificativa,
            confianca=tag_sugerida.confianca,
            status=tag_sugerida.status,
            precisa_atencao=tag_precisa_atencao(tag_sugerida.confianca),
        ),
    )


@router.get("/{documento_id}/arquivo", response_class=PlainTextResponse)
async def obter_arquivo(
    documento_id: int,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> str:
    """
    Serve o conteúdo do documento — é o "link do documento oficial" citado
    no README. Reaplica a mesma checagem de RBAC de app/core/security.py e
    audita o acesso, já que este endpoint pode ser acessado diretamente
    (não só por quem passou pela busca).
    """
    ip_request = request.client.host if request.client else None
    acesso_permitido, motivo = await validar_acesso(db, usuario.id, documento_id)

    await registrar_acesso(
        db, usuario.id, documento_id,
        AcessoResultado.PERMITIDO if acesso_permitido else AcessoResultado.ACESSO_NEGADO,
        motivo_negacao=None if acesso_permitido else motivo,
        ip_request=ip_request,
    )

    if not acesso_permitido:
        codigo = status.HTTP_404_NOT_FOUND if motivo == "documento_nao_encontrado" else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=codigo, detail="Acesso negado a este documento")

    documento = await db.get(Documento, documento_id)
    return (UPLOADS_DIR.parent / documento.caminho_arquivo).read_text(encoding="utf-8")


async def _extrair_texto(conteudo: Optional[str], arquivo: Optional[UploadFile]) -> str:
    """Resolve o texto do documento a partir do campo 'conteudo' ou do 'arquivo' .txt."""
    if arquivo is not None:
        if not (arquivo.filename or "").lower().endswith(".txt"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Apenas arquivos .txt são aceitos neste protótipo",
            )
        dados = await arquivo.read()
        if len(dados) > TAMANHO_MAXIMO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo muito grande (máximo 2 MB)",
            )
        try:
            texto = dados.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo precisa estar em UTF-8",
            )
    elif conteudo:
        texto = conteudo
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Envie 'conteudo' (texto) ou 'arquivo' (.txt)",
        )

    texto = texto.strip()
    if not texto:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Documento vazio")
    return texto


def _salvar_texto(titulo: str, texto: str) -> Path:
    """Persiste o texto ingerido em uploads/ e retorna o caminho relativo ao projeto."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", titulo.lower()).strip("-")[:60] or "documento"
    nome_arquivo = f"{slug}-{uuid.uuid4().hex[:8]}.txt"
    caminho = UPLOADS_DIR / nome_arquivo
    caminho.write_text(texto, encoding="utf-8")
    return caminho.relative_to(UPLOADS_DIR.parent)
