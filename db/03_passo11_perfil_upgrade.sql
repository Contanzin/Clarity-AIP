-- ============================================================================
-- CLARITY A.I.P - MIGRAÇÃO: PERFIL, ADMIN E UPGRADE DE TAG (Passo 11)
-- ============================================================================
-- Aditiva: para bancos já existentes (criados antes deste passo), sem
-- apagar dados. Uma instalação nova já recebe tudo isto via
-- 01_init_schema.sql — rode este arquivo só se seu banco já existia antes.
--
-- Uso:
--   psql -h localhost -U clarity_user -d clarity_aip -f db/03_passo11_perfil_upgrade.sql
-- ============================================================================

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS cargo VARCHAR(255),
    ADD COLUMN IF NOT EXISTS departamento VARCHAR(50);

CREATE TABLE IF NOT EXISTS solicitacoes_upgrade_tag (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tag_solicitada VARCHAR(50) NOT NULL CHECK (tag_solicitada ~ '^[A-Za-z]+\d+$'),
    justificativa TEXT NOT NULL,
    status tag_sugestao_status NOT NULL DEFAULT 'pendente_revisao',
    criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revisada_em TIMESTAMP,
    revisor_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    comentario_revisor TEXT
);

CREATE INDEX IF NOT EXISTS idx_solicitacoes_upgrade_usuario ON solicitacoes_upgrade_tag(usuario_id);
CREATE INDEX IF NOT EXISTS idx_solicitacoes_upgrade_status ON solicitacoes_upgrade_tag(status);

-- Dados de perfil para os usuários seed já existentes (ver 02_seed_data.sql).
UPDATE usuarios SET cargo = 'Analista de Marketing', departamento = 'Marketing' WHERE email = 'alice@claro.corp';
UPDATE usuarios SET cargo = 'Gerente de Vendas', departamento = 'Vendas' WHERE email = 'bob@claro.corp';
UPDATE usuarios SET cargo = 'Administradora do Sistema', departamento = 'TI', is_admin = TRUE WHERE email = 'carol@claro.corp';
UPDATE usuarios SET cargo = 'Analista de Suporte', departamento = 'Suporte' WHERE email = 'david@claro.corp';

COMMIT;
