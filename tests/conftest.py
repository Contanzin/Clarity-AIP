"""
Fixtures compartilhadas dos testes.

Os testes rodam contra o banco de desenvolvimento real (não um banco de
teste separado) — mesma filosofia usada durante todo o desenvolvimento
deste projeto ("sempre testar de verdade"). Cada fixture que cria dados
limpa depois de si (yield + teardown), pra não sujar o banco usado pra
demo manual.

Chamadas ao Gemini são mockadas nos testes que envolvem ingestão/busca —
isso evita depender de rede/quota durante os testes e mantém resultados
determinísticos, mas os outros trechos (auth, RBAC, banco) rodam de
verdade.
"""

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import SessionLocal
from app.main import app
from app.models import Usuario, UsuarioTag

EMBEDDING_FAKE = [0.1] * 768


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def usuario_com_tag():
    """Usuário de teste ativo com a tag Marketing2 — limpo ao final."""
    email = f"teste-{uuid.uuid4().hex[:8]}@teste.claro.corp"
    async with SessionLocal() as db:
        usuario = Usuario(nome="Usuario de Teste", email=email, ativo=True)
        db.add(usuario)
        await db.flush()
        db.add(UsuarioTag(usuario_id=usuario.id, tag="Marketing2"))
        await db.commit()
        usuario_id = usuario.id

    yield {"id": usuario_id, "email": email}

    async with SessionLocal() as db:
        obj = await db.get(Usuario, usuario_id)
        if obj is not None:
            await db.delete(obj)
            await db.commit()


@pytest_asyncio.fixture
async def usuario_sem_tag():
    """Usuário de teste ativo, sem nenhuma tag de acesso — limpo ao final."""
    email = f"teste-{uuid.uuid4().hex[:8]}@teste.claro.corp"
    async with SessionLocal() as db:
        usuario = Usuario(nome="Usuario Sem Tag", email=email, ativo=True)
        db.add(usuario)
        await db.commit()
        usuario_id = usuario.id

    yield {"id": usuario_id, "email": email}

    async with SessionLocal() as db:
        obj = await db.get(Usuario, usuario_id)
        if obj is not None:
            await db.delete(obj)
            await db.commit()
