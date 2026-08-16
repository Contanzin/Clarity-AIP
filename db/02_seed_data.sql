-- ============================================================================
-- CLARITY A.I.P - DADOS INICIAIS PARA TESTE
-- ============================================================================
-- Este arquivo contém dados fake/sintéticos para testes e desenvolvimento.
-- NUNCA USE DADOS REAIS DA CLARO sem ter um plano pago do Gemini!
--
-- Uso:
--   psql -h localhost -U clarity_user -d clarity_aip -f db/02_seed_data.sql
-- ============================================================================

-- ============================================================================
-- 1. USUÁRIOS DE TESTE
-- ============================================================================

INSERT INTO usuarios (nome, email, ativo) VALUES
    ('Alice Silva', 'alice@claro.corp', TRUE),
    ('Bob Santos', 'bob@claro.corp', TRUE),
    ('Carol Oliveira', 'carol@claro.corp', TRUE),
    ('David Pereira', 'david@claro.corp', FALSE);  -- Inativo

-- ============================================================================
-- 2. TAGS DE ACESSO (Permissões)
-- ============================================================================

-- Alice: Acesso a Marketing (nível 1-2) e Dados (nível 1)
INSERT INTO usuario_tags (usuario_id, tag, atribuida_por_usuario_id, observacoes) VALUES
    (1, 'Marketing1', 1, 'Acesso básico a Marketing'),
    (1, 'Marketing2', 1, 'Acesso expandido a Marketing'),
    (1, 'Dados1', 1, 'Acesso limitado a Dados');

-- Bob: Acesso a Vendas (nível 1-3)
INSERT INTO usuario_tags (usuario_id, tag, atribuida_por_usuario_id, observacoes) VALUES
    (2, 'Vendas1', 1, 'Acesso básico a Vendas'),
    (2, 'Vendas2', 1, 'Acesso intermediário a Vendas'),
    (2, 'Vendas3', 1, 'Acesso completo a Vendas');

-- Carol: Acesso a tudo (curador/admin)
INSERT INTO usuario_tags (usuario_id, tag, atribuida_por_usuario_id, observacoes) VALUES
    (3, 'Marketing3', 1, 'Acesso total a Marketing'),
    (3, 'Dados3', 1, 'Acesso total a Dados'),
    (3, 'Vendas3', 1, 'Acesso total a Vendas'),
    (3, 'Suporte3', 1, 'Acesso total a Suporte');

-- David: Inativo (não deve acessar nada)
-- (sem tags)

-- ============================================================================
-- 3. DOCUMENTOS (Pendentes de aprovação)
-- ============================================================================

-- Documento 1: "Políticas de Desconto em Marketing"
-- Status: pendente (ainda não foi aprovado)
-- Area: Marketing, Nível: 2
INSERT INTO documentos 
    (titulo, area, nivel_acesso_exigido, status, caminho_arquivo, usuario_criador_id)
VALUES
    (
        'Políticas de Desconto em Marketing',
        'Marketing',
        2,
        'pendente',
        '/docs/marketing/politicas_desconto.pdf',
        1
    );

-- Documento 2: "Dados de Clientes Premium"
-- Status: pendente
-- Area: Dados, Nível: 3 (muito confidencial)
INSERT INTO documentos
    (titulo, area, nivel_acesso_exigido, status, caminho_arquivo, usuario_criador_id)
VALUES
    (
        'Dados de Clientes Premium',
        'Dados',
        3,
        'pendente',
        '/docs/dados/clientes_premium.xlsx',
        1
    );

-- Documento 3: "Metas de Vendas 2026"
-- Status: pendente
-- Area: Vendas, Nível: 1
INSERT INTO documentos
    (titulo, area, nivel_acesso_exigido, status, caminho_arquivo, usuario_criador_id)
VALUES
    (
        'Metas de Vendas 2026',
        'Vendas',
        1,
        'pendente',
        '/docs/vendas/metas_2026.pdf',
        2
    );

-- ============================================================================
-- 4. SUGESTÕES DE TAGS (O que a IA sugeriu)
-- ============================================================================

-- Sugestão para Doc 1: A IA sugeriu "Marketing2" com confiança 0.92
INSERT INTO tags_sugeridas
    (documento_id, tag_sugerida, justificativa, confianca, status)
VALUES
    (
        1,
        'Marketing2',
        'Documento contém políticas de desconto interno que não são públicas. Nível 2 apropriado. Trechos: "desconto máximo 20%", "aprovação gerencial obrigatória"',
        0.92,
        'pendente_revisao'
    );

-- Sugestão para Doc 2: A IA sugeriu "Dados3" com confiança 0.88
INSERT INTO tags_sugeridas
    (documento_id, tag_sugerida, justificativa, confianca, status)
VALUES
    (
        2,
        'Dados3',
        'Dados sensíveis de clientes (nomes, CPF, histórico). Claramente nível 3. Trechos: "CPF mascarado", "dados pessoais"',
        0.88,
        'pendente_revisao'
    );

-- Sugestão para Doc 3: A IA sugeriu "Vendas1" com confiança 0.65 (baixa confiança!)
INSERT INTO tags_sugeridas
    (documento_id, tag_sugerida, justificativa, confianca, status)
VALUES
    (
        3,
        'Vendas1',
        'Documento sobre metas anuais. Público? Documento não deixa claro. Trechos: "metas comerciais", "targets"',
        0.65,
        'pendente_revisao'
    );

-- ============================================================================
-- 5. EXEMPLO: TESTE MANUAL DE VALIDAÇÃO DE ACESSO
-- ============================================================================
-- Após carregar este arquivo, você pode testar assim:
--
-- SELECT validar_acesso(1, 1) AS alice_acessa_doc1;
-- -- Resultado esperado: FALSE (documento ainda está pendente)
--
-- Depois de aprovar a sugestão do documento 1:
-- UPDATE documentos SET status = 'aprovado' WHERE id = 1;
-- SELECT validar_acesso(1, 1) AS alice_acessa_doc1;
-- -- Resultado esperado: TRUE (Alice tem Marketing2, documento é Marketing2, aprovado)
--
-- SELECT validar_acesso(2, 1) AS bob_acessa_doc1;
-- -- Resultado esperado: FALSE (Bob só tem Vendas1-3, não tem Marketing)

COMMIT;
