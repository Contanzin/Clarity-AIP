async def test_login_sucesso(client, usuario_com_tag):
    resp = await client.post("/api/v1/auth/login", json={"email": usuario_com_tag["email"]})
    assert resp.status_code == 200
    assert resp.json()["email"] == usuario_com_tag["email"]


async def test_login_email_inexistente(client):
    resp = await client.post("/api/v1/auth/login", json={"email": "ninguem@teste.claro.corp"})
    assert resp.status_code == 401


async def test_login_usuario_inativo(client):
    # david@claro.corp existe no seed de dados como usuário inativo
    resp = await client.post("/api/v1/auth/login", json={"email": "david@claro.corp"})
    assert resp.status_code == 401


async def test_me_sem_sessao(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_login_logout_me(client, usuario_com_tag):
    await client.post("/api/v1/auth/login", json={"email": usuario_com_tag["email"]})

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200

    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
