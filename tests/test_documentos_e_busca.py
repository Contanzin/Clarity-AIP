"""
Teste de integração do fluxo principal do produto: ingestão -> aprovação
-> busca (com filtro de permissão) -> negação de acesso a quem não tem tag.

As chamadas ao Gemini são mockadas (embedding fixo, sugestão fixa) para o
teste não depender de rede/quota e ser determinístico — o resto (auth,
RBAC, banco, endpoints) roda de verdade contra o banco de desenvolvimento.
"""

from unittest.mock import AsyncMock

from app.core.database import SessionLocal
from app.core.gemini import SugestaoTagIA
from app.models import Documento

EMBEDDING_FAKE = [0.1] * 768


async def test_fluxo_completo_ingerir_aprovar_buscar_e_restringir(
    client, usuario_com_tag, usuario_sem_tag, monkeypatch
):
    monkeypatch.setattr(
        "app.api.routes.documentos.gerar_embedding", AsyncMock(return_value=EMBEDDING_FAKE)
    )
    monkeypatch.setattr(
        "app.api.routes.documentos.sugerir_tag",
        AsyncMock(return_value=SugestaoTagIA(
            area="Marketing", nivel=2, justificativa="Motivo de teste.", confianca=0.9,
        )),
    )
    monkeypatch.setattr(
        "app.api.routes.busca.gerar_embedding", AsyncMock(return_value=EMBEDDING_FAKE)
    )
    monkeypatch.setattr(
        "app.api.routes.busca.gerar_resumo_executivo", AsyncMock(return_value="Resumo de teste.")
    )

    # 1. Ingestão (usuário com tag Marketing2 cria o documento)
    await client.post("/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "12345"})
    resp = await client.post(
        "/api/v1/documentos",
        data={"titulo": "Documento de Teste Automatizado", "conteudo": "Conteúdo de teste para o pipeline de ingestão."},
    )
    assert resp.status_code == 201
    dados = resp.json()
    documento_id = dados["id"]
    tag_id = dados["tag_sugerida"]["id"]
    assert dados["status"] == "pendente"
    assert dados["area"] == "Marketing"

    try:
        # 2. Antes de aprovado, mesmo quem tem a tag não encontra na busca
        resp = await client.post("/api/v1/busca", json={"pergunta": "pergunta de teste"})
        assert resp.status_code == 200
        assert resp.json()["resultado"] == "nao_encontrado"

        # 3. Aprovação (o próprio usuário, que já tem Marketing2, pode curar)
        resp = await client.post(f"/api/v1/tags-sugeridas/{tag_id}/aprovar", json={"comentario": "ok"})
        assert resp.status_code == 200
        assert resp.json()["documento"]["status"] == "aprovado"

        # 4. Agora a busca encontra, com resumo gerado
        resp = await client.post("/api/v1/busca", json={"pergunta": "pergunta de teste"})
        assert resp.status_code == 200
        dados_busca = resp.json()
        assert dados_busca["resultado"] == "encontrado"
        assert dados_busca["documento_id"] == documento_id
        assert dados_busca["resumo_executivo"] == "Resumo de teste."

        # 5. Usuário SEM nenhuma tag: mesma pergunta -> restrito, sem vazar título/resumo
        await client.post("/api/v1/auth/login", json={"email": usuario_sem_tag["email"], "senha": "12345"})
        resp = await client.post("/api/v1/busca", json={"pergunta": "pergunta de teste"})
        assert resp.status_code == 200
        dados_restrito = resp.json()
        assert dados_restrito["resultado"] == "restrito"
        assert dados_restrito["tag_necessaria"] == "Marketing2"
        assert dados_restrito["titulo"] is None
        assert dados_restrito["resumo_executivo"] is None
    finally:
        async with SessionLocal() as db:
            doc = await db.get(Documento, documento_id)
            if doc is not None:
                await db.delete(doc)
                await db.commit()


async def test_busca_exige_autenticacao(client):
    resp = await client.post("/api/v1/busca", json={"pergunta": "qualquer coisa"})
    assert resp.status_code == 401


async def test_ingerir_documento_sem_conteudo_da_erro(client, usuario_com_tag):
    await client.post("/api/v1/auth/login", json={"email": usuario_com_tag["email"], "senha": "12345"})
    resp = await client.post("/api/v1/documentos", data={"titulo": "Sem conteúdo nem arquivo"})
    assert resp.status_code == 400
