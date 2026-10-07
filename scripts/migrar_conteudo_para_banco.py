"""
Backfill de conteudo_texto para bancos que já tinham documentos antes da
migração db/05_conteudo_em_banco.sql (conteúdo saiu de uploads/*.txt e foi
pro banco). Rodar uma vez, depois de aplicar o ALTER TABLE daquele arquivo.

Uso:
    python scripts/migrar_conteudo_para_banco.py
"""

import asyncio
from pathlib import Path

from sqlalchemy import select, text

from app.core.database import SessionLocal, engine
from app.models import Documento

BASE_DIR = Path(__file__).resolve().parent.parent


async def main():
    async with SessionLocal() as db:
        result = await db.execute(select(Documento).where(Documento.conteudo_texto.is_(None)))
        documentos = result.scalars().all()

        for documento in documentos:
            caminho = BASE_DIR / documento.caminho_arquivo
            if caminho.exists():
                documento.conteudo_texto = caminho.read_text(encoding="utf-8")
                print(f"Documento {documento.id}: migrado de {caminho}")
            else:
                documento.conteudo_texto = f"[Conteúdo original não encontrado em disco na migração] {documento.titulo}"
                print(f"Documento {documento.id}: arquivo não encontrado, usei um placeholder")

        await db.commit()

    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE documentos ALTER COLUMN conteudo_texto SET NOT NULL"))
    print("Coluna conteudo_texto agora é NOT NULL. Migração concluída.")


if __name__ == "__main__":
    asyncio.run(main())
