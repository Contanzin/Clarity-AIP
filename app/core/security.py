"""
Módulo de segurança e controle de acesso do Clarity A.I.P.

Contém funções para:
- Validar se um usuário tem acesso a um documento
- Registrar acessos em auditoria
- Extrair informações de tags
"""

import re
import logging
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models import Usuario, Documento, LogAccesso, AcessoResultado, DocumentoStatus
from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# VALIDAÇÃO DE ACESSO
# ============================================================================

async def validar_acesso(
    db: AsyncSession,
    usuario_id: int,
    documento_id: int
) -> Tuple[bool, Optional[str]]:
    """
    Valida se um usuário tem acesso a um documento.

    Regras:
    1. Usuário deve estar ativo
    2. Documento deve estar aprovado (status='aprovado')
    3. Usuário deve ter uma tag "Area+Nivel" onde:
       - Area coincide com documento.area
       - Nivel >= documento.nivel_acesso_exigido

    Args:
        db: AsyncSession do banco
        usuario_id: ID do usuário
        documento_id: ID do documento

    Returns:
        (acesso_permitido: bool, motivo_negacao: Optional[str])

        Se acesso_permitido=True: motivo_negacao=None
        Se acesso_permitido=False: motivo_negacao indica por quê
            - 'usuario_inativo': usuário não está ativo
            - 'documento_pendente': documento ainda não foi aprovado
            - 'tag_insuficiente': usuário não tem a tag necessária
            - 'usuario_nao_encontrado': usuário não existe
            - 'documento_nao_encontrado': documento não existe
    """

    # 1. Verificar se usuário existe e está ativo
    stmt_usuario = select(Usuario).where(Usuario.id == usuario_id)
    result_usuario = await db.execute(stmt_usuario)
    usuario = result_usuario.scalar_one_or_none()

    if usuario is None:
        return False, "usuario_nao_encontrado"

    if not usuario.ativo:
        return False, "usuario_inativo"

    # 2. Verificar se documento existe e está aprovado
    stmt_documento = select(Documento).where(Documento.id == documento_id)
    result_documento = await db.execute(stmt_documento)
    documento = result_documento.scalar_one_or_none()

    if documento is None:
        return False, "documento_nao_encontrado"

    if documento.status != DocumentoStatus.APROVADO:
        return False, "documento_pendente"

    # 3. Verificar se usuário tem tag apropriada
    # Carrega tags do usuário (lazy load se não foram carregadas)
    if not hasattr(usuario, "tags") or usuario.tags is None:
        stmt_usuario_com_tags = select(Usuario).where(Usuario.id == usuario_id).options(
            selectinload(Usuario.tags)
        )
        result_usuario_com_tags = await db.execute(stmt_usuario_com_tags)
        usuario = result_usuario_com_tags.scalar_one()

    # Verifica se alguma tag do usuário permite acesso ao documento
    acesso_permitido = _verificar_tags_usuario(usuario.tags, documento.area, documento.nivel_acesso_exigido)

    if not acesso_permitido:
        return False, "tag_insuficiente"

    return True, None


def usuario_pode_curar(usuario: Usuario, tag: str) -> bool:
    """
    Verifica se um usuário pode aprovar/corrigir uma sugestão de tag.

    Reaproveita o RBAC existente em vez de criar um papel de "curador"
    separado: só pode liberar acesso a "Area+Nivel" quem já teria, ele
    mesmo, acesso a um documento com essa mesma tag. Ninguém aprova acesso
    a algo que não pode ver.

    Args:
        usuario: Usuario (com tags carregadas)
        tag: Tag no formato "Area+Nivel" (ex: "Marketing2") a ser aprovada

    Returns:
        True se o usuário tem uma tag de área/nível suficiente
    """
    area, nivel = extrair_area_nivel(tag)
    if not area:
        return False
    return _verificar_tags_usuario(usuario.tags, area, nivel)


def _verificar_tags_usuario(tags, area_documento: str, nivel_documento: int) -> bool:
    """
    Verifica se as tags de um usuário permitem acesso a um documento.

    Args:
        tags: Lista de UsuarioTag
        area_documento: Área do documento (ex: "Marketing")
        nivel_documento: Nível exigido (ex: 2)

    Returns:
        True se alguma tag do usuário permite acesso
    """
    for tag_obj in tags:
        tag_str = tag_obj.tag
        area, nivel = extrair_area_nivel(tag_str)

        # Área deve bater e nível deve ser >= ao exigido
        if area == area_documento and nivel >= nivel_documento:
            return True

    return False


def extrair_area_nivel(tag: str) -> Tuple[str, int]:
    """
    Extrai área e nível de uma tag no formato "Area+Nivel".

    Exemplos:
        "Marketing2" → ("Marketing", 2)
        "Dados1" → ("Dados", 1)

    Args:
        tag: String no formato "Area+Nivel"

    Returns:
        (area: str, nivel: int)
        Se formato inválido, retorna ("", 0)
    """
    match = re.match(r"^([A-Za-z]+)(\d+)$", tag)
    if not match:
        return "", 0

    area = match.group(1)
    nivel = int(match.group(2))

    return area, nivel


# ============================================================================
# LOGGING DE AUDITORIA
# ============================================================================

async def registrar_acesso(
    db: AsyncSession,
    usuario_id: int,
    documento_id: Optional[int],
    resultado: AcessoResultado,
    motivo_negacao: Optional[str] = None,
    ip_request: Optional[str] = None,
    query_texto: Optional[str] = None,
) -> LogAccesso:
    """
    Registra um acesso/tentativa de acesso em logs_acesso.

    Toda ação (sucesso ou falha) deve ser auditada aqui.

    Args:
        db: AsyncSession
        usuario_id: ID do usuário
        documento_id: ID do documento (opcional)
        resultado: AcessoResultado (PERMITIDO, ACESSO_NEGADO, DOCUMENTO_PENDENTE)
        motivo_negacao: Motivo técnico se resultado != PERMITIDO
        ip_request: IP de origem (opcional)
        query_texto: Texto da busca/pergunta (opcional)

    Returns:
        LogAccesso criado
    """
    log = LogAccesso(
        usuario_id=usuario_id,
        documento_id=documento_id,
        resultado=resultado,
        motivo_negacao=motivo_negacao,
        ip_request=ip_request,
        query_texto=query_texto,
    )

    db.add(log)
    await db.commit()

    logger.info(
        f"Acesso registrado: usuario_id={usuario_id}, documento_id={documento_id}, "
        f"resultado={resultado}, motivo={motivo_negacao}"
    )

    return log


# ============================================================================
# HELPERS PARA SUGESTÕES DE TAGS
# ============================================================================

def tag_precisa_atencao(confianca: float) -> bool:
    """
    Verifica se uma sugestão de tag precisa de atenção especial na revisão.

    Sugestões com confiança < min_confidence_no_warning devem ser destacadas.

    Args:
        confianca: Confiança da sugestão (0.0-1.0)

    Returns:
        True se confiança é baixa (< 0.7 por padrão)
    """
    return confianca < settings.min_confidence_no_warning


def validar_formato_tag(tag: str) -> bool:
    """
    Valida se uma tag segue o formato "Area+Nivel".

    Args:
        tag: String a validar

    Returns:
        True se o formato é válido
    """
    return bool(re.match(r"^[A-Za-z]+\d+$", tag))


# ============================================================================
# HELPERS PARA USUÁRIOS
# ============================================================================

async def obter_usuario_por_email(db: AsyncSession, email: str) -> Optional[Usuario]:
    """
    Busca um usuário pelo email.

    Args:
        db: AsyncSession
        email: Email do usuário

    Returns:
        Usuario ou None
    """
    stmt = select(Usuario).where(Usuario.email == email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def obter_usuario_com_tags(db: AsyncSession, usuario_id: int) -> Optional[Usuario]:
    """
    Busca um usuário e carrega suas tags de acesso (eager load).

    Args:
        db: AsyncSession
        usuario_id: ID do usuário

    Returns:
        Usuario com tags carregadas, ou None
    """
    stmt = select(Usuario).where(Usuario.id == usuario_id).options(
        selectinload(Usuario.tags)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def obter_usuario_com_tags_por_email(db: AsyncSession, email: str) -> Optional[Usuario]:
    """
    Busca um usuário pelo email e carrega suas tags de acesso (eager load).

    Args:
        db: AsyncSession
        email: Email do usuário

    Returns:
        Usuario com tags carregadas, ou None
    """
    stmt = select(Usuario).where(Usuario.email == email).options(
        selectinload(Usuario.tags)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
