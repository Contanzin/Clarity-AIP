"""
Autenticação do Clarity A.I.P.

Autenticação simplificada para o protótipo: login apenas por email (sem
senha). O usuário precisa já existir na tabela `usuarios` e estar ativo —
não há self-signup. A sessão é mantida em um cookie assinado (Starlette
SessionMiddleware, configurado em app/main.py com SESSION_SECRET).

Por que sem senha agora: o objetivo do protótipo é validar o fluxo de
RBAC/busca, não reimplementar autenticação. Em produção a Claro teria
AD/SSO corporativo. Por isso a verificação de identidade fica isolada
atrás de AuthProvider — trocar para AD/SSO depois é implementar uma nova
classe aqui, sem tocar nas rotas ou no resto da aplicação.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import obter_usuario_com_tags, obter_usuario_com_tags_por_email
from app.models import Usuario

logger = logging.getLogger(__name__)


# ============================================================================
# AUTH PROVIDER (plugável)
# ============================================================================

class AuthProvider(ABC):
    """
    Interface para verificação de identidade.

    Trocar a implementação (ex: EmailAuthProvider -> ADAuthProvider) é a
    única mudança necessária para integrar um provedor de identidade real.
    """

    @abstractmethod
    async def autenticar(self, db: AsyncSession, email: str) -> Optional[Usuario]:
        """Retorna o Usuario autenticado, ou None se as credenciais forem inválidas."""
        raise NotImplementedError


class EmailAuthProvider(AuthProvider):
    """
    Provider do protótipo: identidade = existir com esse email e estar ativo.

    Sem verificação de senha. Adequado apenas para demo com dados sintéticos.
    """

    async def autenticar(self, db: AsyncSession, email: str) -> Optional[Usuario]:
        usuario = await obter_usuario_com_tags_por_email(db, email)
        if usuario is None or not usuario.ativo:
            return None
        return usuario


def get_auth_provider() -> AuthProvider:
    """Ponto único de configuração de qual AuthProvider está ativo."""
    return EmailAuthProvider()


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
