"""
Autenticação do Clarity A.I.P.

Login por email + senha. O usuário precisa já existir na tabela `usuarios`
e estar ativo — não há self-signup. A sessão é mantida em um cookie
assinado (Starlette SessionMiddleware, configurado em app/main.py com
SESSION_SECRET). Senhas nunca são guardadas em texto puro — ver
gerar_hash_senha/verificar_senha abaixo (PBKDF2-HMAC-SHA256 com salt
aleatório por usuário, biblioteca padrão do Python).

A verificação de identidade fica isolada atrás de AuthProvider — integrar
um provedor de identidade corporativo (AD/SSO) depois é só implementar uma
nova classe aqui, sem tocar nas rotas ou no resto da aplicação.
"""

import hashlib
import hmac
import logging
import secrets
from abc import ABC, abstractmethod
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import obter_usuario_com_tags, obter_usuario_com_tags_por_email
from app.models import Usuario

logger = logging.getLogger(__name__)


# ============================================================================
# HASH DE SENHA
# ============================================================================

_ALGORITMO_HASH = "pbkdf2_sha256"
_ITERACOES_HASH = 260_000


def gerar_hash_senha(senha: str) -> str:
    """Gera um hash salgado de senha, no formato 'algoritmo$iteracoes$salt$hash' (todos em hex)."""
    salt = secrets.token_hex(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), _ITERACOES_HASH)
    return f"{_ALGORITMO_HASH}${_ITERACOES_HASH}${salt}${hash_bytes.hex()}"


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Confere uma senha em texto puro contra um hash gerado por gerar_hash_senha."""
    try:
        algoritmo, iteracoes_str, salt, hash_hex = hash_armazenado.split("$")
    except ValueError:
        return False
    if algoritmo != _ALGORITMO_HASH:
        return False
    calculado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), int(iteracoes_str))
    return hmac.compare_digest(calculado.hex(), hash_hex)


# ============================================================================
# AUTH PROVIDER (plugável)
# ============================================================================

class AuthProvider(ABC):
    """
    Interface para verificação de identidade.

    Trocar a implementação (ex: SenhaAuthProvider -> ADAuthProvider) é a
    única mudança necessária para integrar um provedor de identidade real.
    """

    @abstractmethod
    async def autenticar(self, db: AsyncSession, email: str, senha: str) -> Optional[Usuario]:
        """Retorna o Usuario autenticado, ou None se as credenciais forem inválidas."""
        raise NotImplementedError


class SenhaAuthProvider(AuthProvider):
    """Identidade = email cadastrado, ativo, e senha confere com o hash salvo."""

    async def autenticar(self, db: AsyncSession, email: str, senha: str) -> Optional[Usuario]:
        usuario = await obter_usuario_com_tags_por_email(db, email)
        if usuario is None or not usuario.ativo:
            return None
        if not verificar_senha(senha, usuario.senha_hash):
            return None
        return usuario


def get_auth_provider() -> AuthProvider:
    """Ponto único de configuração de qual AuthProvider está ativo."""
    return SenhaAuthProvider()


# ============================================================================
# SESSÃO
# ============================================================================

SESSION_KEY_USUARIO_ID = "usuario_id"


def iniciar_sessao(request: Request, usuario: Usuario) -> None:
    """Grava o usuário autenticado na sessão (cookie assinado)."""
    request.session[SESSION_KEY_USUARIO_ID] = usuario.id


def encerrar_sessao(request: Request) -> None:
    """Remove o usuário autenticado da sessão."""
    request.session.pop(SESSION_KEY_USUARIO_ID, None)


# ============================================================================
# DEPENDENCIES DE FASTAPI
# ============================================================================

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """
    Dependency que exige um usuário autenticado.

    Uso:
        @app.get("/rota-protegida")
        async def rota(usuario: Usuario = Depends(get_current_user)):
            ...

    Levanta 401 se não houver sessão válida, usuário não existir mais, ou
    tiver sido desativado depois do login.
    """
    usuario_id = request.session.get(SESSION_KEY_USUARIO_ID)
    if usuario_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")

    usuario = await obter_usuario_com_tags(db, usuario_id)
    if usuario is None or not usuario.ativo:
        encerrar_sessao(request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")

    return usuario


async def get_admin_user(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    """Dependency que exige um usuário autenticado E admin — ver app/api/routes/admin.py."""
    if not usuario.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return usuario
