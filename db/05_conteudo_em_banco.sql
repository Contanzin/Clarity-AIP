-- ============================================================================
-- CLARITY A.I.P - MIGRAÇÃO: CONTEÚDO DO DOCUMENTO NO BANCO (não em disco)
-- ============================================================================
-- Aditiva: para bancos já existentes. Uma instalação nova já recebe
-- conteudo_texto via 01_init_schema.sql/02_seed_data.sql.
--
-- Hosts grátis (Render free tier, por exemplo) apagam o filesystem a cada
-- deploy/spin-down — por isso o texto do documento passou a morar no banco
-- (conteudo_texto) em vez de uploads/*.txt. Esta migração só adiciona a
-- coluna; o backfill dos documentos já existentes (ler o arquivo de
-- uploads/ e gravar no banco) é feito por scripts/migrar_conteudo_para_banco.py,
-- porque SQL puro não lê arquivos locais de forma portátil.
--
-- Uso:
--   psql -h localhost -U clarity_user -d clarity_aip -f db/05_conteudo_em_banco.sql
--   python scripts/migrar_conteudo_para_banco.py
-- ============================================================================

ALTER TABLE documentos ADD COLUMN IF NOT EXISTS conteudo_texto TEXT;

-- NOT NULL só é aplicado depois do backfill (ver scripts/migrar_conteudo_para_banco.py).
