# Passo 3 — Modelos ORM e Configuração do Banco

## 📦 Arquivos criados

### 1. `app/config.py` — Configuração centralizada

Carrega todas as variáveis de ambiente via `pydantic` e disponibiliza como `settings` global.

**Variáveis suportadas**:
- **App**: `APP_ENV`, `DEBUG`, `HOST`, `PORT`
- **Database**: `DATABASE_URL`, `POSTGRES_*` (host, port, db, user, password)
- **Gemini**: `GEMINI_API_KEY`, `GEMINI_MODEL`, `ENABLE_GEMINI_PRIVACY_NOTICE`
- **Segurança**: `SESSION_SECRET`
- **Aplicação**: `EMBEDDING_DIMENSION` (padrão 768), `MIN_CONFIDENCE_NO_WARNING` (padrão 0.7)

**Uso**:
```python
from app.config import settings

print(settings.database_url)  # Acessa a variável
print(settings.debug)  # True/False
```

---

### 2. `app/core/database.py` — Setup do SQLAlchemy

Configura o engine assíncrono e session factory.

**Componentes principais**:
- **`Base`**: Classe declarativa para herdar em modelos ORM
- **`engine`**: SQLAlchemy AsyncEngine com `asyncpg` driver
- **`SessionLocal`**: Factory para criar AsyncSession
- **`get_db()`**: Dependency injection para endpoints FastAPI
- **`init_db()`**: Cria tabelas (fallback; tabelas já existem via SQL puro)
- **`close_db()`**: Limpeza ao desligar a app

**Uso em endpoints**:
```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

@app.get("/usuarios")
async def listar_usuarios(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario))
    usuarios = result.scalars().all()
    return usuarios
```

---

### 3. `app/models.py` — Modelos ORM

Mapeia as 5 tabelas do banco para classes Python com SQLAlchemy.

#### Enums (Tipos customizados)

```python
class DocumentoStatus(str, enum.Enum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"

class TagSugestaoStatus(str, enum.Enum):
    PENDENTE_REVISAO = "pendente_revisao"
    APROVADA = "aprovada"
    REJEITADA = "rejeitada"

class AcessoResultado(str, enum.Enum):
    PERMITIDO = "permitido"
    ACESSO_NEGADO = "acesso_negado"
    DOCUMENTO_PENDENTE = "documento_pendente"
```

#### Modelos

| Tabela | Classe | Relacionamentos |
|--------|--------|-----------------|
| `usuarios` | `Usuario` | tags (1:N), logs_acesso (1:N), documentos_criados (1:N) |
| `usuario_tags` | `UsuarioTag` | usuario (N:1), atribuida_por (N:1) |
| `documentos` | `Documento` | usuario_criador (N:1), tag_sugerida (1:1), logs_acesso (1:N) |
| `tags_sugeridas` | `TagSugerida` | documento (1:N), revisor (N:1) |
| `logs_acesso` | `LogAccesso` | usuario (N:1), documento (N:1) |

**Features importantes**:

- ✅ **Lazy load configurável**: `lazy="selectin"` carrega relacionamentos automaticamente
- ✅ **Cascades**: Deletar um usuário deleta suas tags automaticamente (`cascade="all, delete-orphan"`)
- ✅ **Constraints no ORM**: Validação de formato de tags, níveis positivos, confiança 0-1
- ✅ **Timestamps automáticos**: `default=datetime.utcnow`, `onupdate=datetime.utcnow`
- ✅ **Índices**: Estrategicamente criados para performance

**Exemplo de uso**:
```python
from app.models import Usuario, UsuarioTag
from sqlalchemy import select

# Query com eager load de tags
stmt = select(Usuario).options(selectinload(Usuario.tags))
result = await db.execute(stmt)
usuario = result.scalar_one()

# Acessar tags (já carregadas)
for tag in usuario.tags:
    print(tag.tag)  # Ex: "Marketing2"
```

---

### 4. `app/core/security.py` — Controle de acesso

Funções reutilizáveis para validar permissões, registrar acessos, e manipular tags.

#### `validar_acesso(db, usuario_id, documento_id) → (bool, Optional[str])`

Implementa a lógica de RBAC do sistema.

```python
from app.core.security import validar_acesso

acesso_permitido, motivo = await validar_acesso(db, usuario_id=1, documento_id=42)

if acesso_permitido:
    print("✅ Acesso concedido")
else:
    print(f"❌ Acesso negado: {motivo}")
    # Motivos possíveis:
    # - 'usuario_inativo'
    # - 'documento_pendente'
    # - 'tag_insuficiente'
    # - 'usuario_nao_encontrado'
    # - 'documento_nao_encontrado'
```

**Regras implementadas**:
1. Usuário deve estar ativo
2. Documento deve estar aprovado
3. Usuário deve ter tag "Area+Nivel" com nível >= necessário

---

#### `registrar_acesso(db, usuario_id, documento_id, resultado, ...)`

Registra toda ação em auditoria (logs_acesso).

```python
from app.core.security import registrar_acesso
from app.models import AcessoResultado

# Registrar acesso bem-sucedido
await registrar_acesso(
    db,
    usuario_id=1,
    documento_id=42,
    resultado=AcessoResultado.PERMITIDO,
    ip_request="192.168.1.1",
    query_texto="Como é a política de desconto?"
)

# Registrar acesso negado
await registrar_acesso(
    db,
    usuario_id=1,
    documento_id=42,
    resultado=AcessoResultado.ACESSO_NEGADO,
    motivo_negacao="tag_insuficiente",
    ip_request="192.168.1.1",
)
```

---

#### `tag_precisa_atencao(confianca: float) → bool`

Verifica se uma sugestão de tag deve ser destacada na UI.

```python
if tag_precisa_atencao(sugestao.confianca):
    # Destacar em amarelo/vermelho na interface
    print(f"⚠️ Confiança baixa: {sugestao.confianca}")
```

---

#### Helpers adicionais

- **`_extrair_area_nivel(tag: str)`**: Extrai ("Area", Nivel) de "Area+Nivel"
- **`_verificar_tags_usuario(tags, area, nivel)`**: Verifica se alguma tag permite acesso
- **`validar_formato_tag(tag: str)`**: Valida formato "Area+Nivel"
- **`obter_usuario_por_email(db, email)`**: Busca usuário
- **`obter_usuario_com_tags(db, usuario_id)`**: Busca usuário e carrega tags

---

### 5. `app/main.py` — Aplicação principal (atualizada)

Integra tudo: configuração, banco, models, event handlers.

**Event handlers**:
- `@app.on_event("startup")`: Inicializa banco ao ligar
- `@app.on_event("shutdown")`: Limpa conexões ao desligar

**Endpoints já existentes**:
- `GET /health`: Health check simples
- `GET /api/v1/debug/db-info`: [DEBUG] Info de conexão

---

## 🏗️ Arquitetura de relacionamentos

```
Usuario (1)
├─ (1:N) UsuarioTag → tags de acesso
├─ (1:N) LogAccesso → histórico de acessos
├─ (1:N) Documento → documentos que criou
└─ (1:N) TagSugerida → tags que revisou

Documento (1)
├─ (N:1) Usuario → quem criou
├─ (1:1) TagSugerida → sugestão de tag
└─ (1:N) LogAccesso → acessos ao doc

TagSugerida (1)
├─ (N:1) Documento → documento sugerido
└─ (N:1) Usuario → revisor

LogAccesso (1)
├─ (N:1) Usuario → quem tentou acessar
└─ (N:1) Documento → qual documento
```

---

## ✅ Validação de implementação

Para verificar se tudo foi bem configurado:

```bash
# 1. Ativar venv (se não estiver)
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate      # Windows

# 2. Testar import dos modelos
python -c "from app.models import Usuario, Documento, UsuarioTag, TagSugerida, LogAccesso; print('✅ Modelos importados com sucesso')"

# 3. Testar config
python -c "from app.config import settings; print(f'✅ Config carregada: {settings.app_name}')"

# 4. Testar database (vai falhar se banco não estiver pronto, é normal)
python -c "from app.core.database import engine, Base; print('✅ Database configurado')"
```

---

## 🚀 Próximos passos

**Passo 4**: Autenticação e módulo de usuários
- Endpoint de login simples
- Criar usuários
- Listar permissões de um usuário

O ORM está pronto e reutilizável em todos os endpoints futuros!
