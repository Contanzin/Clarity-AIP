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

-- Senha padrão de todos os usuários de teste: "12345" (hash PBKDF2 abaixo).
-- Trocável em /perfil após o login.
INSERT INTO usuarios (nome, email, senha_hash, ativo, cargo, departamento, is_admin) VALUES
    ('Alice Silva', 'alice@claro.corp', 'pbkdf2_sha256$260000$2f16ee636107a76c31e5eb09a1dd0ed3$ed9382aa5bd03b716e58f91aa0b9c679c83a5ba251e23b83327430c0bd09e746', TRUE, 'Analista de Marketing', 'Marketing', FALSE),
    ('Bob Santos', 'bob@claro.corp', 'pbkdf2_sha256$260000$4752b2d612952daf96ba5639de5fe394$fa1fd23bc6c6d7b5e14695f2ee702046d475a77075a7197d02ebb1c43b977278', TRUE, 'Gerente de Vendas', 'Vendas', FALSE),
    ('Carol Oliveira', 'carol@claro.corp', 'pbkdf2_sha256$260000$0a752dd7f0d0c1bd83356aaabc2f977c$b6fa48516b8388762ee0a5325db5f2da87f4ab3478114ccb9e4c2a4f9016e146', TRUE, 'Administradora do Sistema', 'TI', TRUE),
    ('David Pereira', 'david@claro.corp', 'pbkdf2_sha256$260000$f14d3f4fdbf375d6bf5ec3483a378b7f$9e7baee21d0e469a855aa05d120d018b7b48f40c8188899c03e916bfaae88f95', FALSE, 'Analista de Suporte', 'Suporte', FALSE);  -- Inativo

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
    (titulo, area, nivel_acesso_exigido, status, caminho_arquivo, conteudo_texto, usuario_criador_id)
VALUES
    (
        'Políticas de Desconto em Marketing',
        'Marketing',
        2,
        'pendente',
        'politicas-desconto-marketing-seed',
        'Dado sintético de teste. Política de descontos: desconto máximo de 20% para revendedores, exige aprovação gerencial acima desse valor.',
        1
    );

-- Documento 2: "Dados de Clientes Premium"
-- Status: pendente
-- Area: Dados, Nível: 3 (muito confidencial)
INSERT INTO documentos
    (titulo, area, nivel_acesso_exigido, status, caminho_arquivo, conteudo_texto, usuario_criador_id)
VALUES
    (
        'Dados de Clientes Premium',
        'Dados',
        3,
        'pendente',
        'dados-clientes-premium-seed',
        'Dado sintético de teste. Relatório de clientes premium: nomes, CPF mascarado e histórico de compras dos últimos 12 meses.',
        1
    );

-- Documento 3: "Metas de Vendas 2026"
-- Status: pendente
-- Area: Vendas, Nível: 1
INSERT INTO documentos
    (titulo, area, nivel_acesso_exigido, status, caminho_arquivo, conteudo_texto, usuario_criador_id)
VALUES
    (
        'Metas de Vendas 2026',
        'Vendas',
        1,
        'pendente',
        'metas-vendas-2026-seed',
        'Dado sintético de teste. Metas comerciais de 2026: crescimento de 15% em receita e expansão para 3 novas regiões.',
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
