# Modelagem do Banco de Dados - Clarity A.I.P

## 📋 Visão geral

O banco PostgreSQL usa 7 tabelas principais + 1 função helper para implementar:
1. **Autenticação e autorização** (RBAC) via `usuarios` + `usuario_tags`
2. **Controle de acesso granular** (documentos, níveis, áreas)
3. **Sugestão de tags com revisão humana** (fail-safe para segurança)
4. **Busca semântica segura** via `pgvector` (embeddings)
5. **Auditoria completa** (logs_acesso)

---

## 🗂️ Estrutura das tabelas

### `usuarios`
Armazena colaboradores da Claro que acessam o sistema.

```sql
id (PK)
nome (VARCHAR)
email (VARCHAR, UNIQUE)
ativo (BOOLEAN)
data_criacao (TIMESTAMP)
data_atualizacao (TIMESTAMP)
```

**Decisão de design**: As permissões **não** estão em JSONB nesta tabela. Estão em uma tabela relacional separada (`usuario_tags`). Por quê?
- ✅ Auditável: cada mudança de permissão tem timestamp de quando foi atribuída e por quem
- ✅ Evolutivo: futuro permite histórico de permissões
- ✅ Seguro: evita erros de alteração em massa (ex: não "acidentalmente" dá todas as tags a um usuário)
- ❌ Um pouco mais complexo: requer JOIN para obter permissões

---

### `usuario_tags`
Relação N:M entre usuários e suas tags de acesso.

```sql
id (PK)
usuario_id (FK → usuarios)
tag (VARCHAR) -- formato: "Area+Nivel" (ex: "Marketing2", "Dados1")
atribuida_por_usuario_id (FK → usuarios)
data_atribuicao (TIMESTAMP)
observacoes (TEXT)
```

**Tag format**: `"Area+Nivel"`
- Exemplos: `Marketing1`, `Marketing2`, `Dados3`, `Vendas1`
- Um usuário pode ter múltiplas tags: `['Marketing2', 'Dados1']` = acessa docs de Marketing nível ≤2 e Dados nível ≤1

**Validação**: Constraint `CHECK (tag ~ '^[A-Za-z]+\d+$')` garante que a tag sempre segue o padrão.

**Índices**: 
- Por usuário (rápido obter permissões de um usuário)
- Por tag (rápido saber quem tem uma permissão)

---

### `documentos`
Metadados e embeddings dos documentos.

```sql
id (PK)
titulo (VARCHAR)
area (VARCHAR) -- ex: "Marketing", "Dados"
nivel_acesso_exigido (INT) -- 1, 2, 3, 4...
status (ENUM: 'pendente' | 'aprovado')
caminho_arquivo (VARCHAR)
resumo_executivo (TEXT)
embedding (vector) -- pgvector: embedding de alta dimensão
data_criacao (TIMESTAMP)
data_atualizacao (TIMESTAMP)
usuario_criador_id (FK → usuarios)
```

**Status**: 
- `'pendente'`: Documento enviado, aguardando aprovação da tag sugerida → **inacessível**
- `'aprovado'`: Tag foi aprovada, documento pronto → **acessível** (se usuário tem permissão)

**Acesso**: Um usuário com tag `Marketing2` pode acessar um documento se:
- `documento.status = 'aprovado'`
- `documento.area = 'Marketing'`
- `documento.nivel_acesso_exigido <= 2`

**Embedding**: Vetor de 768 dimensões (depende do modelo de embedding). Usado para busca semântica.

**Índices**:
- Por status (listar documentos pendentes)
- Por area (filtros)
- Vetor (busca semântica via `IVFFlat`)

---

### `tags_sugeridas`
Rastreia sugestões de tags feitas pela IA e sua aprovação.

```sql
id (PK)
documento_id (FK → documentos, UNIQUE)
tag_sugerida (VARCHAR)
justificativa (TEXT)
confianca (DECIMAL 0.0-1.0)
status (ENUM: 'pendente_revisao' | 'aprovada' | 'rejeitada')
criada_em (TIMESTAMP)
revisada_em (TIMESTAMP)
revisor_id (FK → usuarios)
comentario_revisor (TEXT)
```

**Workflow**:
1. Documento é enviado com status `'pendente'`
2. IA gera embedding e sugere tag (confiança, justificativa)
3. Humano revisa em status `'pendente_revisao'`
4. Humano aprova (status `'aprovada'`) ou rejeita (status `'rejeitada'`)
5. Se aprovada, documento status muda para `'aprovado'`

**Confiança**: 0.0-1.0
- < 0.7: **destacar visualmente** na UI para revisor dar atenção extra
- ≥ 0.7: OK, mas ainda deve ser revisado

**UNIQUE(documento_id)**: Cada documento tem apenas uma sugestão ativa.

---

### `logs_acesso`
Auditoria obrigatória de TODAS as consultas/acessos.

```sql
id (PK, BIGSERIAL para volume alto)
usuario_id (FK → usuarios)
documento_id (FK → documentos, nullable)
resultado (ENUM: 'permitido' | 'acesso_negado' | 'documento_pendente')
motivo_negacao (VARCHAR)
ip_request (VARCHAR)
query_texto (TEXT)
timestamp (TIMESTAMP)
```

**Resultado**:
- `'permitido'`: Usuário acessou o documento
- `'acesso_negado'`: Usuário não tem tag/permissão
- `'documento_pendente'`: Documento existe mas ainda está em revisão

**Motivo_negacao**: 
- `'tag_insuficiente'`
- `'documento_pendente'`
- `'usuario_inativo'`
- etc.

**Índices**: Por usuário, documento, timestamp, resultado (para queries de auditoria)

---

### ENUMS (Tipos customizados)
```sql
documento_status: 'pendente', 'aprovado'
tag_sugestao_status: 'pendente_revisao', 'aprovada', 'rejeitada'
acesso_resultado: 'permitido', 'acesso_negado', 'documento_pendente'
```

---

## 🔐 Funções SQL para segurança

### `validar_acesso(usuario_id, documento_id) → BOOLEAN`

Encapsula a lógica de controle de acesso:

```sql
SELECT validar_acesso(1, 42);  -- TRUE se usuário 1 pode acessar doc 42
```

Regra de negócio:
1. Usuário deve estar ativo
2. Documento deve estar aprovado (não pendente)
3. Usuário deve ter tag da forma `"Area+Nivel"` onde:
   - `Area` coincide com `documento.area`
   - `Nivel` ≥ `documento.nivel_acesso_exigido`

Esta função é usada na aplicação antes de:
- Retornar um documento
- Fazer busca semântica
- Registrar log de acesso

---

## ⚠️ Decisões críticas de segurança

### 1. Fail-safe
- Documentos **começam com status `'pendente'`** e são **sempre inacessíveis**
- Só ficam acessíveis quando status é `'aprovado'`
- Regra: é mais fácil bloquear que liberar

### 2. Filtro de permissão ANTES de busca semântica
Quando o usuário faz uma pergunta, a query busca assim:

```sql
SELECT d.id, d.titulo, d.resumo_executivo
FROM documentos d
INNER JOIN usuario_tags ut 
    ON d.area = substring(ut.tag from '^[A-Za-z]+')
    AND d.nivel_acesso_exigido <= CAST(regexp_replace(ut.tag, '\d+$', '') AS INT)
WHERE d.status = 'aprovado'
  AND ut.usuario_id = $1
  AND d.embedding <-> $2 < 0.3  -- busca semântica (cosine distance)
ORDER BY d.embedding <-> $2
LIMIT 5;
```

O **INNER JOIN** garante que a IA nunca vê documentos inacessíveis. Não é filtro de aplicação — é **filtro no banco**.

### 3. Auditoria obrigatória
Toda ação (bem ou mal-sucedida) é registrada em `logs_acesso`. Isso permite:
- Rastrear intent de acesso
- Detectar padrões de abuso
- Conformidade regulatória

### 4. Sem permissões em JSONB
Permissões em `usuario_tags` (tabela relacional), não em JSONB no campo de usuários. Isso:
- Permite auditoria granular
- Evita alterações silenciosas
- Facilita histórico futuro

---

## 🚀 Próximos passos

1. **Setup do banco**:
   - Windows: `.\db\setup.ps1`
   - Linux/Mac: `bash db/setup.sh`

2. **Models ORM** (Passo 3):
   - SQLAlchemy para mapear tabelas para Python
   - Funções de acesso em `app/core/security.py`

3. **Endpoints de teste** (Passo 4+):
   - Login simples
   - Criar documento
   - Sugerir tags
   - Buscar documentos

---

## 📚 Referências

- **pgvector**: https://github.com/pgvector/pgvector
- **PostgreSQL JSON**: https://www.postgresql.org/docs/current/datatype-json.html
- **PostgreSQL RLS**: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
