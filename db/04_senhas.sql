-- ============================================================================
-- CLARITY A.I.P - MIGRAÇÃO: SENHAS (autenticação real)
-- ============================================================================
-- Aditiva: para bancos já existentes. Uma instalação nova já recebe
-- senha_hash via 01_init_schema.sql/02_seed_data.sql — rode este arquivo só
-- se seu banco já existia antes deste passo.
--
-- Uso:
--   psql -h localhost -U clarity_user -d clarity_aip -f db/04_senhas.sql
-- ============================================================================

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS senha_hash VARCHAR(255);

-- Senha padrão "12345" (hash PBKDF2-HMAC-SHA256, ver app/core/auth.py).
UPDATE usuarios SET senha_hash = 'pbkdf2_sha256$260000$2f16ee636107a76c31e5eb09a1dd0ed3$ed9382aa5bd03b716e58f91aa0b9c679c83a5ba251e23b83327430c0bd09e746' WHERE email = 'alice@claro.corp';
UPDATE usuarios SET senha_hash = 'pbkdf2_sha256$260000$4752b2d612952daf96ba5639de5fe394$fa1fd23bc6c6d7b5e14695f2ee702046d475a77075a7197d02ebb1c43b977278' WHERE email = 'bob@claro.corp';
UPDATE usuarios SET senha_hash = 'pbkdf2_sha256$260000$0a752dd7f0d0c1bd83356aaabc2f977c$b6fa48516b8388762ee0a5325db5f2da87f4ab3478114ccb9e4c2a4f9016e146' WHERE email = 'carol@claro.corp';
UPDATE usuarios SET senha_hash = 'pbkdf2_sha256$260000$f14d3f4fdbf375d6bf5ec3483a378b7f$9e7baee21d0e469a855aa05d120d018b7b48f40c8188899c03e916bfaae88f95' WHERE email = 'david@claro.corp';

-- Qualquer outro usuário já existente no banco (ex: criado via testes/demo
-- manual) também recebe a senha padrão "12345", pra não quebrar com NOT NULL.
UPDATE usuarios SET senha_hash = 'pbkdf2_sha256$260000$2f16ee636107a76c31e5eb09a1dd0ed3$ed9382aa5bd03b716e58f91aa0b9c679c83a5ba251e23b83327430c0bd09e746' WHERE senha_hash IS NULL;

ALTER TABLE usuarios ALTER COLUMN senha_hash SET NOT NULL;

COMMIT;
