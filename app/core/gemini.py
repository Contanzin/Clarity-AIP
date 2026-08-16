"""
Integração com a API do Gemini (Google AI Studio).

⚠️ AVISO DE PRIVACIDADE: o free tier do Gemini pode reter o conteúdo das
requisições para melhorar os modelos do Google. Este protótipo deve ser
usado apenas com dados sintéticos/anonimizados — NUNCA envie documentos
reais da Claro sem um plano pago com garantias contratuais de privacidade.
Ver README.md e ENABLE_GEMINI_PRIVACY_NOTICE em app/config.py.

Usa o pacote `google-genai` (o antigo `google-generativeai` foi
descontinuado pelo Google em 2026 — "all support has ended"). A SDK é
síncrona; as funções aqui rodam as chamadas de rede em thread separada
(asyncio.to_thread) para não bloquear o event loop do FastAPI.

Nomes de modelo do Gemini são retirados com frequência (já aconteceu uma
vez neste projeto: text-embedding-004 e gemini-1.5-flash pararam de
existir). Por isso usamos "gemini-flash-latest", um alias que a Google
mantém apontando para o modelo flash atual recomendado, em vez de fixar
uma versão específica.
"""

import asyncio
import json
import logging
import re
from typing import Optional

from google import genai
from google.genai import types
from google.genai.errors import APIError, ServerError
from pydantic import BaseModel, Field, field_validator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.areas import AREAS_VALIDAS

logger = logging.getLogger(__name__)

_client: Optional[genai.Client] = None

# Valor padrão do .env.example — se ainda estiver assim, a chave não foi
# configurada de verdade (evita bater na API do Google com uma chave inválida
# e vazar o erro cru pro cliente).
_PLACEHOLDER_API_KEY = "your_gemini_api_key_here"

EMBEDDING_MODEL = "gemini-embedding-001"


class GeminiNaoConfiguradoError(RuntimeError):
    """Levantado quando GEMINI_API_KEY não está definida (ou ainda é o placeholder) no .env."""


class GeminiIndisponivelError(RuntimeError):
    """Levantado quando a chamada à API do Gemini falha (chave inválida, quota, rede, etc.)."""


def _obter_cliente() -> genai.Client:
    global _client
    if not settings.gemini_api_key or settings.gemini_api_key == _PLACEHOLDER_API_KEY:
        raise GeminiNaoConfiguradoError(
            "GEMINI_API_KEY não configurada — defina no .env para usar recursos de IA."
        )
    if settings.enable_gemini_privacy_notice:
        logger.warning(
            "Chamando a API do Gemini (free tier pode reter dados para treinar "
            "modelos do Google). Use apenas dados sintéticos/anonimizados."
        )
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


# O free tier do Gemini responde "503 UNAVAILABLE / high demand" com alguma
# frequência (observado várias vezes durante o desenvolvimento deste passo)
# — é transitório, então vale tentar de novo com backoff. Erros 4xx
# (ClientError: chave inválida, modelo inexistente) não são retentados, pois
# não se resolvem sozinhos.
_retry_em_sobrecarga = retry(
    retry=retry_if_exception_type(ServerError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)


async def gerar_embedding(texto: str) -> list[float]:
    """Gera o embedding (vetor) de um texto via Gemini."""
    client = _obter_cliente()

    @_retry_em_sobrecarga
    def _chamar() -> list[float]:
        resultado = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texto,
            config=types.EmbedContentConfig(output_dimensionality=settings.embedding_dimension),
        )
        return list(resultado.embeddings[0].values)

    try:
        return await asyncio.to_thread(_chamar)
    except APIError as exc:
        logger.error("Falha ao gerar embedding via Gemini: %s", exc)
        raise GeminiIndisponivelError("Falha ao gerar embedding via Gemini") from exc


_PROMPT_RESUMO = """Resuma o documento abaixo de forma executiva.

Regras estritas:
- Use APENAS informações que estão literalmente escritas no documento.
- NUNCA invente, infira ou complete informações que não estão no texto.
- Se o documento não deixar algo claro, não especule sobre isso.
- Seja objetivo: no máximo 4 frases.

Documento:
---
{documento}
---

Resumo executivo:"""


async def gerar_resumo_executivo(texto: str) -> str:
    """
    Gera um resumo executivo extrativo/fiel ao documento via Gemini.

    Extrativo por design: a decisão de produto é nunca responder livremente
    sobre o conteúdo, só resumir de forma fiel — ver README.md.
    """
    client = _obter_cliente()
    prompt = _PROMPT_RESUMO.format(documento=texto)

    @_retry_em_sobrecarga
    def _chamar() -> str:
        resposta = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        return resposta.text.strip()

    try:
        return await asyncio.to_thread(_chamar)
    except APIError as exc:
        logger.error("Falha ao gerar resumo executivo via Gemini: %s", exc)
        raise GeminiIndisponivelError("Falha ao gerar resumo executivo via Gemini") from exc


class SugestaoTagIA(BaseModel):
    """Sugestão de tag feita pela IA para um documento (resposta estruturada do Gemini)."""

    area: str
    nivel: int = Field(ge=1, le=4)
    justificativa: str
    confianca: float = Field(ge=0.0, le=1.0)

    @field_validator("area")
    @classmethod
    def area_valida(cls, v: str) -> str:
        if v not in AREAS_VALIDAS:
            raise ValueError(f"Área '{v}' fora da lista permitida: {AREAS_VALIDAS}")
        return v


_PROMPT_TEMPLATE = """Você é um classificador de documentos corporativos internos da Claro.

Analise o documento abaixo e sugira:
- "area": exatamente uma destas opções, sem alterar a grafia: {areas}
- "nivel": um inteiro de 1 a 4 (1 = acesso amplo, 4 = extremamente confidencial)
- "justificativa": trechos ou motivos concretos do documento que embasam a escolha
- "confianca": um número de 0.0 a 1.0 representando sua confiança nessa classificação

Responda SOMENTE com um JSON no formato:
{{"area": "...", "nivel": N, "justificativa": "...", "confianca": 0.0}}

Documento:
---
{documento}
---
"""

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


async def sugerir_tag(texto: str) -> SugestaoTagIA:
    """Pede ao Gemini uma sugestão de área + nível de acesso para um documento."""
    client = _obter_cliente()

    prompt = _PROMPT_TEMPLATE.format(areas=", ".join(AREAS_VALIDAS), documento=texto)

    @_retry_em_sobrecarga
    def _chamar() -> str:
        resposta = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return resposta.text

    try:
        texto_resposta = await asyncio.to_thread(_chamar)
    except APIError as exc:
        logger.error("Falha ao chamar o Gemini para sugerir tag: %s", exc)
        raise GeminiIndisponivelError("Falha ao chamar o Gemini para sugerir tag") from exc

    return _parsear_sugestao(texto_resposta)


def _parsear_sugestao(texto_resposta: str) -> SugestaoTagIA:
    """
    Interpreta o JSON da sugestão.

    Alguns modelos ocasionalmente intercalam texto de raciocínio antes/depois
    do JSON mesmo com response_mime_type="application/json" — por isso, se o
    parse direto falhar, extraímos o maior bloco {...} da resposta como
    fallback antes de desistir.
    """
    for candidato in (texto_resposta, _extrair_bloco_json(texto_resposta)):
        if candidato is None:
            continue
        try:
            return SugestaoTagIA(**json.loads(candidato))
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    logger.error("Resposta da IA não pôde ser interpretada: %r", texto_resposta)
    raise ValueError("Falha ao interpretar sugestão da IA: resposta não é um JSON válido")


def _extrair_bloco_json(texto: str) -> Optional[str]:
    match = _JSON_OBJECT_RE.search(texto)
    return match.group(0) if match else None
