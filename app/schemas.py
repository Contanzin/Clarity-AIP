"""
Schemas Pydantic (request/response) do Clarity A.I.P.

Separados dos modelos ORM (app/models.py) para não vazar detalhes de
implementação do banco (ex: relacionamentos, colunas internas) na API.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ============================================================================
# USUÁRIOS
# ============================================================================

class UsuarioCriar(BaseModel):
    """Payload para criar um novo usuário."""
    nome: str = Field(min_length=1, max_length=255)
    email: EmailStr


class UsuarioTagOut(BaseModel):
    """Representação pública de uma tag de acesso."""
    tag: str
    data_atribuicao: datetime

    model_config = {"from_attributes": True}


class UsuarioOut(BaseModel):
    """Representação pública de um usuário (sem dados sensíveis)."""
    id: int
    nome: str
    email: str
    ativo: bool

    model_config = {"from_attributes": True}


class UsuarioComTagsOut(UsuarioOut):
    """Usuário incluindo suas tags de acesso (permissões)."""
    tags: list[UsuarioTagOut] = []


# ============================================================================
# AUTENTICAÇÃO
# ============================================================================

class LoginRequest(BaseModel):
    """
    Payload de login do protótipo.

    Autenticação simplificada: apenas o email é verificado (usuário precisa
    existir e estar ativo). Sem senha nesta fase — ver app/core/auth.py para
    a justificativa e como plugar um provedor real (AD/SSO) no futuro.
    """
    email: EmailStr


# ============================================================================
# DOCUMENTOS
# ============================================================================

class TagSugeridaOut(BaseModel):
    """Sugestão de tag feita pela IA, pendente de revisão humana (Passo 6)."""
    id: int
    tag_sugerida: str
    justificativa: str
    confianca: float
    status: str
    precisa_atencao: bool


class DocumentoOut(BaseModel):
    """Documento recém-ingerido, com a sugestão de tag da IA."""
    id: int
    titulo: str
    area: str
    nivel_acesso_exigido: int
    status: str
    caminho_arquivo: str
    data_criacao: datetime
    tag_sugerida: TagSugeridaOut

    model_config = {"from_attributes": True}


# ============================================================================
# REVISÃO DE TAGS (curadoria — Passo 6)
# ============================================================================

class DocumentoResumoOut(BaseModel):
    """Resumo do documento associado a uma sugestão de tag em revisão."""
    id: int
    titulo: str
    status: str


class TagSugeridaDetalheOut(BaseModel):
    """Sugestão de tag com o contexto necessário para o curador decidir."""
    id: int
    tag_sugerida: str
    justificativa: str
    confianca: float
    status: str
    precisa_atencao: bool
    revisor_id: Optional[int] = None
    revisada_em: Optional[datetime] = None
    comentario_revisor: Optional[str] = None
    documento: DocumentoResumoOut


class AprovarTagRequest(BaseModel):
    """
    Aprova a sugestão da IA, opcionalmente corrigindo área e/ou nível.

    Se area/nivel não forem informados, aprova exatamente como a IA sugeriu.
    """
    area: Optional[str] = None
    nivel: Optional[int] = Field(default=None, ge=1, le=4)
    comentario: Optional[str] = None


class RejeitarTagRequest(BaseModel):
    """Rejeita a sugestão da IA — o documento permanece 'pendente' (inacessível)."""
    comentario: str = Field(min_length=1)


# ============================================================================
# BUSCA (Passo 7 — o core do produto)
# ============================================================================

class BuscaRequest(BaseModel):
    """Pergunta em linguagem natural."""
    pergunta: str = Field(min_length=1, max_length=2000)


class BuscaResponse(BaseModel):
    """
    Resposta da busca. `resultado` é um dos três estados do produto:

    - "encontrado": documento acessível encontrado — inclui link + resumo.
    - "restrito": o documento mais relevante existe, mas o usuário não tem
      acesso — inclui a tag necessária, nunca título/conteúdo.
    - "nao_encontrado": nenhum documento aprovado relevante o suficiente.
    """
    resultado: str
    mensagem: str
    documento_id: Optional[int] = None
    titulo: Optional[str] = None
    link: Optional[str] = None
    resumo_executivo: Optional[str] = None
    tag_necessaria: Optional[str] = None
