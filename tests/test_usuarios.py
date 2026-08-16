import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Usuario


async def test_criar_usuario(client):
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
    resp = await client.post(
        "/api/v1/usuarios", json={"nome": "Outro Nome", "email": usuario_com_tag["email"]}
    )
    assert resp.status_code == 409
