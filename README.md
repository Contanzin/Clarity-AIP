# Clarity A.I.P

Clarity A.I.P é um protótipo de Knowledge Broker para a operadora de telecom Claro, pensado para responder perguntas corporativas com controle de acesso e baixa chance de alucinação.

## Objetivo

O sistema recebe uma pergunta em linguagem natural, identifica o documento oficial mais relevante, verifica se o usuário tem permissão de acesso e:

- se autorizado: retorna o link do documento oficial e um resumo executivo fiel ao conteúdo do documento;
- se não autorizado: informa que o documento existe, mas o acesso é restrito, e indica a tag de acesso necessária para solicitar liberação;
- se o documento ainda não foi aprovado: informa que ele está pendente e, portanto, não é acessível.

A decisão de design é deliberada: o sistema não responde livremente sobre o conteúdo. Ele aponta, resume de forma extrativa e governa o acesso — a busca vetorial só é feita entre documentos que o usuário já tem permissão de acessar, e a IA nunca gera resumo a partir de um documento restrito.

## Arquitetura

- Backend em Python com FastAPI.
- Banco PostgreSQL com extensão pgvector (dados relacionais de RBAC/ABAC e busca semântica no mesmo banco).
- IA com a API do Gemini (pacote `google-genai`), usada para gerar embeddings, sugerir tags de acesso, e gerar resumos executivos extrativos.
- Interface web simples com Jinja2 + JavaScript puro (sem framework de frontend) — toda a interatividade chama a própria API JSON do backend.
- Driver de banco: asyncpg (assíncrono, via SQLAlchemy).

### Fluxo de governança de documentos

1. Um documento é enviado (`/enviar` ou `POST /api/v1/documentos`) como texto colado ou arquivo `.txt`.
2. A IA gera o embedding e sugere uma tag de área + nível de acesso, com justificativa e confiança. O documento fica `pendente` (inacessível) até revisão humana.
3. Um curador — alguém que já possui, ele mesmo, a tag de acesso equivalente ou superior à sugerida — revisa em `/curadoria` e aprova (com ou sem correção) ou rejeita. Não existe aprovação automática nem em lote.
4. Só então o documento fica `aprovado` e passível de aparecer nas buscas de quem tiver a tag necessária.

## Estrutura do projeto

```text
clarity_aip/
├── app/
│   ├── api/routes/       # Endpoints da API (auth, usuarios, documentos, tags_sugeridas, busca) e páginas HTML
│   ├── core/             # Config, banco, autenticação, RBAC, integração com Gemini
│   ├── static/           # CSS e JS das páginas
│   ├── templates/        # Templates Jinja2 (login, busca, enviar, curadoria)
│   ├── config.py
│   ├── main.py
│   ├── models.py         # Modelos ORM (SQLAlchemy)
│   └── schemas.py        # Schemas Pydantic (request/response da API)
├── db/                   # Schema SQL, dados de teste, scripts de setup do banco
├── scripts/              # Bootstrap de ambiente (Postgres + pgvector no Windows)
├── tests/                # Testes automatizados (pytest)
├── uploads/              # Arquivos de documentos enviados (gitignored)
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
└── venv/
```

## Requisitos

- Python 3.11+ (testado com 3.14)
- PostgreSQL 14+ com a extensão `pgvector` habilitada
- Uma API key do Gemini (gratuita, via [Google AI Studio](https://aistudio.google.com/apikey))

## Configuração inicial

### 1. Ambiente Python

```powershell
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### 2. PostgreSQL + pgvector

**Windows**, sem PostgreSQL instalado ainda: rode como Administrador o script de bootstrap, que instala Git, PostgreSQL 17 e o Visual Studio Build Tools, e compila a extensão pgvector a partir do código-fonte oficial:

```powershell
.\scripts\install_postgres_windows.ps1
```

Ele define a senha do superusuário `postgres` como `clarity_dev_superuser` (já é o valor usado em `.env.example`). Se você já tem PostgreSQL 14+ com `pgvector` instalado (Windows, Linux ou macOS), pode pular essa etapa.

### 3. Variáveis de ambiente

```powershell
copy .env.example .env      # Windows
# cp .env.example .env      # Linux/macOS
```

Edite `.env` e preencha `GEMINI_API_KEY` com uma chave gerada em [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (login com conta Google, gratuito). As demais variáveis já vêm com defaults razoáveis para desenvolvimento local.

> ⚠️ O free tier do Gemini pode reter o conteúdo das requisições para melhorar os modelos do Google. Use apenas dados sintéticos/anonimizados neste protótipo — nunca dados reais da Claro sem um plano pago com garantias contratuais de privacidade.

### 4. Banco de dados

```powershell
.\db\setup.ps1               # Windows
# bash db/setup.sh           # Linux/macOS
```

Isso cria o banco `clarity_aip`, o usuário `clarity_user`, habilita o `pgvector` e carrega o schema (`db/01_init_schema.sql`). Opcionalmente, carregue os dados de teste:

```powershell
$env:PGPASSWORD = "clarity_password"
psql -h localhost -U clarity_user -d clarity_aip -f db\02_seed_data.sql
```

Isso cria 4 usuários de teste (login é só por email, sem senha — ver "Autenticação" abaixo).

### 5. Rodar a aplicação

```powershell
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abra **http://127.0.0.1:8000/login** no navegador.

## Autenticação (protótipo)

Login simplificado: apenas o email é verificado (o usuário precisa existir e estar ativo — sem senha). Ver `app/core/auth.py` para a justificativa e o ponto de extensão para um provedor real (AD/SSO) no futuro.

Usuários de teste (`db/02_seed_data.sql`):

| Email | Tags de acesso |
|---|---|
| `alice@claro.corp` | Marketing1, Marketing2, Dados1 |
| `bob@claro.corp` | Vendas1, Vendas2, Vendas3 |
| `carol@claro.corp` | Marketing3, Dados3, Vendas3, Suporte3 |
| `david@claro.corp` | (nenhuma — usuário inativo, não consegue logar) |

## Páginas

- `/login` — entrar com o email
- `/busca` — fazer uma pergunta em linguagem natural
- `/enviar` — enviar um documento (texto ou `.txt`) para a IA classificar
- `/curadoria` — revisar e aprovar/rejeitar sugestões de tag pendentes (só aparece o que o usuário logado já tem clearance para decidir)

## Testes

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
```

Os testes rodam contra o banco de desenvolvimento real (não um banco separado) e limpam os dados que criam ao final. As chamadas ao Gemini são mockadas nos testes de ingestão/busca, para não depender de rede/quota.

## Observação de privacidade

O free tier do Gemini pode usar dados de requisição para melhorar o modelo do Google. No protótipo, isso só é aceitável com dados sintéticos ou anonimizados. Não use dados reais da Claro sem um plano pago com garantias contratuais de privacidade.

## Publicando em um repositório público

Antes de dar `git push`, confira:

- `.env` (onde fica a `GEMINI_API_KEY` real) está no `.gitignore` — nunca deve ser versionado. Só `.env.example`, com valores fictícios, deve ir pro repositório.
- Rode `git status` depois de um `git add` amplo e confira a lista de arquivos antes de commitar.
- Se uma chave real for commitada por engano em algum momento, revogue/gere uma nova em [aistudio.google.com/apikey](https://aistudio.google.com/apikey) imediatamente — remover o arquivo em um commit futuro não apaga a chave do histórico do Git, e repositórios públicos são varridos por bots em minutos.
