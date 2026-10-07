async def test_login_sucesso(client, usuario_com_tag):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "12345"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == usuario_com_tag["email"]


async def test_login_senha_errada(client, usuario_com_tag):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "senha-errada"}
    )
    assert resp.status_code == 401


async def test_login_email_inexistente(client):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "ninguem@teste.claro.corp", "senha": "12345"}
    )
    assert resp.status_code == 401


async def test_login_usuario_inativo(client):
    # david@claro.corp existe no seed de dados como usuário inativo
    resp = await client.post("/api/v1/auth/login", json={"email": "david@claro.corp", "senha": "12345"})
    assert resp.status_code == 401


async def test_me_sem_sessao(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_login_logout_me(client, usuario_com_tag):
    await client.post("/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "12345"})

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200

    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_trocar_senha(client, usuario_com_tag):
    await client.post("/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "12345"})

    resp = await client.post(
        "/api/v1/auth/senha", json={"senha_atual": "12345", "senha_nova": "nova-senha-123"}
    )
    assert resp.status_code == 200

    await client.post("/api/v1/auth/logout")

    resp = await client.post(
        "/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "12345"}
    )
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "nova-senha-123"}
    )
    assert resp.status_code == 200


async def test_trocar_senha_atual_errada(client, usuario_com_tag):
    await client.post("/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "12345"})

    resp = await client.post(
        "/api/v1/auth/senha", json={"senha_atual": "senha-errada", "senha_nova": "nova-senha-123"}
    )
    assert resp.status_code == 401
