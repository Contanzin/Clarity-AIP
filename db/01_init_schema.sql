-- ============================================================================
-- CLARITY A.I.P - SCHEMA INICIAL
-- ============================================================================
-- Autor: Equipe Clarity
-- Descrição: Schema de banco de dados para o sistema de Knowledge Broker
--            com controle de acesso (RBAC) e busca semântica via pgvector.
--
-- IMPORTANTE DE SEGURANÇA:
-- - Toda a lógica de acesso é relacional (joins, not consultas soltas)
-- - Um usuário NUNCA vê documentos que não tem permissão, nem na busca vetorial
-- - Documentos pendentes são sempre inacessíveis (fail-safe)
-- - Toda ação é auditada em logs_acesso
-- ============================================================================

-- ============================================================================
-- 1. EXTENSÕES NECESSÁRIAS
-- ============================================================================
-- pgvector: permite armazenar e buscar embeddings vetoriais
-- Nota: o nome da extensão registrada é "vector", não "pgvector".
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 2. ENUMS (Tipos de dados customizados)
-- ============================================================================

-- Status de um documento (nunca começa "aprovado")
CREATE TYPE documento_status AS ENUM ('pendente', 'aprovado');

-- Status de uma sugestão de tag feita pela IA
CREATE TYPE tag_sugestao_status AS ENUM ('pendente_revisao', 'aprovada', 'rejeitada');

-- Resultado de uma tentativa de acesso (para auditoria)
CREATE TYPE acesso_resultado AS ENUM ('permitido', 'acesso_negado', 'documento_pendente');

-- ============================================================================
-- 3. TABELA: USUARIOS
-- ============================================================================
-- Armazena informações básicas de colaboradores.
-- As permissões estão em usuario_tags (relação separada), não aqui em JSONB.
-- Isso permite auditoria granular e mudanças de permissão com timestamp.
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    ativo BOOLEAN DEFAULT TRUE,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índice para busca por email (login futura)
CREATE INDEX idx_usuarios_email ON usuarios(email);

-- ============================================================================
-- 4. TABELA: USUARIO_TAGS (Permissões de acesso)
-- ============================================================================
-- Relação N:M entre usuários e suas tags de acesso.
-- Exemplo: usuario_id=1 pode ter tags ['Marketing2', 'Dados1']
--
-- TAG FORMAT: "Area+Nivel"
--   - Area: Marketing, Dados, Vendas, Suporte, etc.
--   - Nivel: 1, 2, 3, 4 (quanto maior, mais confidencial)
--   - Um usuário com "Marketing2" acessa docs Marketing com nível <= 2
CREATE TABLE usuario_tags (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tag VARCHAR(50) NOT NULL,
    -- Quem atribuiu a tag e quando (auditoria)
    atribuida_por_usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    data_atribuicao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observacoes TEXT,
    -- Validação: tags devem seguir padrão "Area+Nivel"
    CONSTRAINT tag_format CHECK (tag ~ '^[A-Za-z]+\d+$'),
    -- Evita duplicação de tags no mesmo usuário
    UNIQUE(usuario_id, tag)
);

-- Índice para busca rápida: dado um usuário, quais tags ele tem
CREATE INDEX idx_usuario_tags_usuario ON usuario_tags(usuario_id);
-- Índice inverso: dada uma tag, quais usuários a possuem
CREATE INDEX idx_usuario_tags_tag ON usuario_tags(tag);

-- ============================================================================
-- 5. TABELA: DOCUMENTOS
-- ============================================================================
-- Armazena metadados e embeddings de documentos.
-- A busca semântica é feita via embedding (pgvector).
-- O acesso é controlado via (area + nivel_acesso_exigido).
CREATE TABLE documentos (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(500) NOT NULL,
    -- Area e nível são extraídos/aprovados pela IA, mas armazenados aqui
    -- Exemplo: area='Marketing', nivel_acesso_exigido=2 significa "Marketing2"
    area VARCHAR(50) NOT NULL,
    nivel_acesso_exigido INT NOT NULL CHECK (nivel_acesso_exigido >= 1),
    -- Status: 'pendente' = aguardando aprovação da tag sugerida
    --         'aprovado' = acessível (se o usuário tem permissão)
    status documento_status NOT NULL DEFAULT 'pendente',
    -- Caminho ou referência para o arquivo original
    -- (pode ser URL, path no S3, ou path local)
    caminho_arquivo VARCHAR(1000) NOT NULL,
    -- Resumo executivo fiel ao documento (gerado pela IA, mas editável)
    resumo_executivo TEXT,
    -- Embedding do documento inteiro (vector de alta dimensão)
    -- Tipo: vector(768) assume embeddings de 768 dimensões
    -- Isso depende do modelo de embedding usado (Gemini, OpenAI, etc.)
    embedding vector(768),
    -- Metadados de auditoria
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usuario_criador_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

-- Índices para melhorar performance
-- 1. Busca por status (para listar documentos pendentes de aprovação)
CREATE INDEX idx_documentos_status ON documentos(status);
-- 2. Busca por area (para filtros de categoria)
CREATE INDEX idx_documentos_area ON documentos(area);
-- 3. Índice vetorial para busca semântica (IVFFlat é eficiente para pgvector)
CREATE INDEX idx_documentos_embedding ON documentos USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================================
-- 6. TABELA: TAGS_SUGERIDAS
-- ============================================================================
-- Rastreia as sugestões de tags feitas pela IA e sua aprovação/rejeição.
-- Workflow:
--   1. Documento é enviado (status='pendente')
--   2. IA sugere uma tag com confiança e justificativa
--   3. Humano revisa (status='pendente_revisao')
--   4. Humano aprova (status='aprovada') ou rejeita (status='rejeitada')
--   5. Se aprovado, documento muda para status='aprovado' e fica acessível
--
-- Isso previne erros de classificação silenciosa que comprometeriam a segurança.
CREATE TABLE tags_sugeridas (
    id SERIAL PRIMARY KEY,
    documento_id INTEGER NOT NULL UNIQUE REFERENCES documentos(id) ON DELETE CASCADE,
    -- Tag sugerida pela IA (formato: "Area+Nivel")
    tag_sugerida VARCHAR(50) NOT NULL,
    -- Trechos do documento que embasam a sugestão (para revisor entender o quê)
    justificativa TEXT NOT NULL,
    -- Confiança da sugestão (0.0 a 1.0)
    -- Sugestões < 0.7 devem ser destacadas na UI para revisão extra
    confianca DECIMAL(3, 2) CHECK (confianca >= 0.0 AND confianca <= 1.0),
    -- Status de revisão
    status tag_sugestao_status NOT NULL DEFAULT 'pendente_revisao',
    -- Timestamps
    criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revisada_em TIMESTAMP,
    -- Quem revisou (NULL enquanto em pendente_revisao)
    revisor_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    -- Comentário do revisor (ex: "Mudei para Marketing3 porque contém dados de clientes")
    comentario_revisor TEXT
);

-- Índices
CREATE INDEX idx_tags_sugeridas_documento ON tags_sugeridas(documento_id);
CREATE INDEX idx_tags_sugeridas_status ON tags_sugeridas(status);
CREATE INDEX idx_tags_sugeridas_confianca ON tags_sugeridas(confianca);

-- ============================================================================
-- 7. TABELA: LOGS_ACESSO
-- ============================================================================
-- Auditoria obrigatória de TODAS as consultas/acessos.
-- Permite:
--   - Investigar abusos
--   - Rastrear quem pediu o quê
--   - Análise de padrões de uso
--
-- Critério: TODA busca (bem-sucedida ou não) é registrada.
CREATE TABLE logs_acesso (
    id BIGSERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    documento_id INTEGER REFERENCES documentos(id) ON DELETE SET NULL,
    -- Resultado da tentativa
    resultado acesso_resultado NOT NULL,
    -- Motivo técnico da negação (se resultado='acesso_negado')
    -- Valores: 'tag_insuficiente', 'documento_pendente', 'usuario_inativo'
    motivo_negacao VARCHAR(100),
    -- IP ou identificador da requisição (para auditoria de origem)
    ip_request VARCHAR(45),
    -- Query que o usuário fez (para rastrear intent)
    query_texto TEXT,
    -- Timestamp
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para auditoria
CREATE INDEX idx_logs_acesso_usuario ON logs_acesso(usuario_id);
CREATE INDEX idx_logs_acesso_documento ON logs_acesso(documento_id);
CREATE INDEX idx_logs_acesso_timestamp ON logs_acesso(timestamp);
CREATE INDEX idx_logs_acesso_resultado ON logs_acesso(resultado);

-- ============================================================================
-- 8. FUNÇÃO HELPER: validar_acesso()
-- ============================================================================
-- Função SQL que encapsula a lógica de controle de acesso.
-- Retorna TRUE se usuário_id tem acesso ao documento_id.
--
-- Regra de acesso:
--   1. Usuário deve estar ativo
--   2. Documento deve estar aprovado (status='aprovado')
--   3. Usuário deve ter uma tag da forma "Area+Nivel" 
--      onde Area = documento.area E Nivel >= documento.nivel_acesso_exigido
--
-- Uso: SELECT validar_acesso(user_id, doc_id);
CREATE OR REPLACE FUNCTION validar_acesso(
    p_usuario_id INTEGER,
    p_documento_id INTEGER
) RETURNS BOOLEAN AS $$
DECLARE
    v_usuario_ativo BOOLEAN;
    v_doc_status documento_status;
    v_doc_area VARCHAR;
    v_doc_nivel INT;
    v_usuario_tem_acesso BOOLEAN;
BEGIN
    -- 1. Verifica se usuário existe e está ativo
    SELECT ativo INTO v_usuario_ativo
    FROM usuarios
    WHERE id = p_usuario_id;
    
    IF v_usuario_ativo IS NULL OR NOT v_usuario_ativo THEN
        RETURN FALSE;
    END IF;
    
    -- 2. Verifica status e area/nivel do documento
    SELECT status, area, nivel_acesso_exigido INTO v_doc_status, v_doc_area, v_doc_nivel
    FROM documentos
    WHERE id = p_documento_id;
    
    -- Documento não existe ou está pendente
    IF v_doc_status IS NULL OR v_doc_status = 'pendente' THEN
        RETURN FALSE;
    END IF;
    
    -- 3. Verifica se usuário tem tag com area+nivel suficiente
    -- Extrai o nome da area e o nível da tag do usuário
    -- Exemplo: tag='Marketing2' → area='Marketing', nivel=2
    v_usuario_tem_acesso := EXISTS (
        SELECT 1
        FROM usuario_tags ut
        WHERE ut.usuario_id = p_usuario_id
          -- A tag começa com v_doc_area
          AND ut.tag ~ ('^' || v_doc_area || '\d+$')
          -- Extrai o número no final da tag e compara
          AND (CAST(regexp_replace(ut.tag, '^[A-Za-z]+(\d+)$', '\1') AS INT)
               >= v_doc_nivel)
    );
    
    RETURN v_usuario_tem_acesso;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- 9. COMENTÁRIOS DE DESIGN E SEGURANÇA
-- ============================================================================
-- FAIL-SAFE:
--   - Por padrão, documentos começam com status='pendente' e são inacessíveis.
--   - Só ficam acessíveis quando status='aprovado'.
--   - Isto é: é mais fácil bloquear do que liberar (melhor para segurança).
--
-- PERMISSÕES NO SQL:
--   - Não usamos políticas de linha (RLS) por simplicidade neste protótipo.
--   - A lógica de controle de acesso está em app/core/security.py (lado da app).
--   - Em produção, poderíamos replicar essas políticas aqui com RLS do PostgreSQL.
--
-- BUSCA SEMÂNTICA SEGURA:
--   - A consulta de busca vetorial DEVE fazer um INNER JOIN com usuario_tags.
--   - Exemplo query (em app/core/search.py):
--     SELECT d.id, d.titulo, d.resumo_executivo, 
--            (embedding <-> $1) as distance
--     FROM documentos d
--     INNER JOIN usuario_tags ut ON d.area = substring(ut.tag from '^[A-Za-z]+')
--                                AND d.nivel_acesso_exigido <= CAST(regexp_replace(ut.tag, '^[A-Za-z]+(\d+)$', '\1') AS INT)
--     WHERE d.status = 'aprovado'
--       AND ut.usuario_id = $2
--     ORDER BY distance LIMIT 5;
--
-- AUDITORIA:
--   - Toda consulta, bem ou mal-sucedida, é registrada em logs_acesso.
--   - Isso permite rastrear intent de acesso e detectar abuso.
--
-- ============================================================================
