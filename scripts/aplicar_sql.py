"""
Roda um arquivo .sql inteiro contra um banco Postgres — alternativa ao
psql (que pode estar bloqueado por política do Windows, como nesta
máquina). Usa asyncpg puro (não SQLAlchemy), que roda scripts com múltiplos
comandos — inclusive a função PL/pgSQL de db/01_init_schema.sql — de uma vez.

Uso:
    python scripts/aplicar_sql.py db/01_init_schema.sql "postgresql://user:senha@host:porta/banco"
    python scripts/aplicar_sql.py db/02_seed_data.sql "postgresql://user:senha@host:porta/banco"
"""

import asyncio
import sys

import asyncpg


async def main(caminho_sql: str, url: str):
    sql = open(caminho_sql, encoding="utf-8").read()
    # asyncpg espera o esquema "postgresql://", não "postgresql+asyncpg://"
    url = url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(url)
    try:
        await conn.execute(sql)
        print(f"OK: {caminho_sql} aplicado com sucesso.")
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python scripts/aplicar_sql.py <arquivo.sql> <database_url>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
