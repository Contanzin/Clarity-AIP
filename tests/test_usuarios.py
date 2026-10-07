import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Usuario


async def _login_admin(client):
    resp = await client.post("/api/v1/auth/login", json={"email": "carol@claro.corp", "senha": "12345"})
    assert resp.status_code == 200


async def test_criar_usuario(client):
    await _login_admin(client)
    email = f"teste-{uuid.uuid4().hex[:8]}@teste.claro.corp"
    try:
        resp = await client.post("/api/v1/usuarios", json={"nome": "Fulano de Teste", "email": email})
        assert resp.status_code == 201
        dados = resp.json()
        assert dados["email"] == email
        assert dados["tags"] == []
    finally:
        async with SessionLocal() as db:
            result = await db.execute(select(Usuario).where(Usuario.email == email))
            usuario = result.scalar_one_or_none()
            if usuario:
                await db.delete(usuario)
                await db.commit()


async def test_criar_usuario_email_duplicado(client, usuario_com_tag):
    await _login_admin(client)
    resp = await client.post(
        "/api/v1/usuarios", json={"nome": "Outro Nome", "email": usuario_com_tag["email"]}
    )
    assert resp.status_code == 409


async def test_criar_usuario_exige_admin(client, usuario_com_tag):
    await client.post("/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "12345"})
    resp = await client.post(
        "/api/v1/usuarios", json={"nome": "Sem Permissao", "email": "naodeveexistir@teste.claro.corp"}
    )
    assert resp.status_code == 403
