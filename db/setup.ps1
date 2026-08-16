# ============================================================================
# CLARITY A.I.P - SETUP DO BANCO DE DADOS (Windows PowerShell)
# ============================================================================
# Descrição: Script para criar o banco PostgreSQL, habilitar extensões,
#            e carregar o schema inicial.
#
# Uso:
#   .\db\setup.ps1
#
# PRÉ-REQUISITOS:
#   - PostgreSQL instalado e rodando (localhost:5432)
#   - Variáveis de ambiente definidas (.env ou manualmente):
#       POSTGRES_SUPERUSER (padrão: postgres) — usado só para criar o banco/usuário
#       POSTGRES_SUPERUSER_PASSWORD           — senha definida na instalação do Postgres
#       POSTGRES_USER / POSTGRES_PASSWORD     — usuário da aplicação a ser criado
#       POSTGRES_DB (padrão: clarity_aip)
# ============================================================================

# Carrega variáveis do .env (simples parsing)
$envFile = ".\.env"
if (Test-Path $envFile) {
    Write-Host "Carregando variáveis de $envFile..." -ForegroundColor Cyan
    Get-Content $envFile | Where-Object { $_ -notmatch "^#" -and $_ -notmatch "^\s*$" } | ForEach-Object {
        $parts = $_ -split "=", 2
        if ($parts.Length -eq 2) {
            [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim())
        }
    }
}

# Defaults e valores do .env
# POSTGRES_USER (superusuário, usado para CONECTAR e criar o resto)
$POSTGRES_USER = if ($env:POSTGRES_SUPERUSER) { $env:POSTGRES_SUPERUSER } else { "postgres" }
$POSTGRES_PASSWORD = if ($env:POSTGRES_SUPERUSER_PASSWORD) { $env:POSTGRES_SUPERUSER_PASSWORD } else { "" }
$POSTGRES_HOST = if ($env:POSTGRES_HOST) { $env:POSTGRES_HOST } else { "localhost" }
$POSTGRES_PORT = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "5432" }
$CLARITY_DB = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "clarity_aip" }
# Usuário da aplicação (o que a app usa em runtime) — diferente do superusuário acima
$CLARITY_USER = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "clarity_user" }
$CLARITY_PASSWORD = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "clarity_password" }

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Clarity A.I.P - Setup do Banco de Dados" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Conectando como: $POSTGRES_USER"
Write-Host "Host: $POSTGRES_HOST`:$POSTGRES_PORT"
Write-Host "Banco a criar: $CLARITY_DB"
Write-Host ""

# Verificar se psql está disponível
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlPath) {
    Write-Host "❌ ERRO: psql não encontrado no PATH" -ForegroundColor Red
    Write-Host "Instale PostgreSQL ou adicione o diretório bin ao PATH" -ForegroundColor Yellow
    exit 1
}

# Função helper para executar psql
function Invoke-Psql {
    param(
        [string]$Database,
        [string]$Command
    )
    
    $env:PGPASSWORD = $POSTGRES_PASSWORD
    if ($Database) {
        psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $Database -c $Command
    } else {
        psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -c $Command
    }
    $env:PGPASSWORD = ""
}

# 1. Criar banco de dados
Write-Host "[1/4] Criando banco de dados '$CLARITY_DB'..." -ForegroundColor Cyan
$dbExists = Invoke-Psql -Database "postgres" -Command "SELECT 1 FROM pg_database WHERE datname = '$CLARITY_DB'" 2>$null | Select-Object -Last 1
if ($dbExists -ne "1") {
    Write-Host "      Criando novo banco..." -ForegroundColor Yellow
    Invoke-Psql -Database "postgres" -Command "CREATE DATABASE $CLARITY_DB;" | Out-Null
} else {
    Write-Host "      Banco já existe" -ForegroundColor Yellow
}
Write-Host "✓ Banco pronto" -ForegroundColor Green

# 2. Criar usuário de aplicação (se não existir)
Write-Host "[2/4] Criando usuário '$CLARITY_USER'..." -ForegroundColor Cyan
$userExists = Invoke-Psql -Database $CLARITY_DB -Command "SELECT 1 FROM pg_user WHERE usename = '$CLARITY_USER'" 2>$null | Select-Object -Last 1
if ($userExists -ne "1") {
    Write-Host "      Criando novo usuário..." -ForegroundColor Yellow
    Invoke-Psql -Database $CLARITY_DB -Command "CREATE USER $CLARITY_USER WITH PASSWORD '$CLARITY_PASSWORD';" | Out-Null
} else {
    Write-Host "      Usuário já existe" -ForegroundColor Yellow
}
Write-Host "✓ Usuário pronto" -ForegroundColor Green

# 3. Conceder permissões
Write-Host "[3/4] Concedendo permissões..." -ForegroundColor Cyan
Invoke-Psql -Database $CLARITY_DB -Command "GRANT ALL PRIVILEGES ON DATABASE $CLARITY_DB TO $CLARITY_USER;" | Out-Null
Invoke-Psql -Database $CLARITY_DB -Command "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $CLARITY_USER;" | Out-Null
# Tabelas com SERIAL/BIGSERIAL criam sequências à parte — sem isso, INSERTs do
# usuário da app falham com "permissão negada para sequência".
Invoke-Psql -Database $CLARITY_DB -Command "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $CLARITY_USER;" | Out-Null
Write-Host "✓ Permissões concedidas" -ForegroundColor Green

# 4. Executar schema
Write-Host "[4/4] Executando schema SQL..." -ForegroundColor Cyan
$schemaFile = "db\01_init_schema.sql"
if (-not (Test-Path $schemaFile)) {
    Write-Host "❌ ERRO: Arquivo $schemaFile não encontrado" -ForegroundColor Red
    exit 1
}
$env:PGPASSWORD = $POSTGRES_PASSWORD
psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $CLARITY_DB -f $schemaFile
$env:PGPASSWORD = ""
Write-Host "✓ Schema carregado" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "✅ Setup completo!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "String de conexão para a app:" -ForegroundColor Cyan
Write-Host "postgresql+asyncpg://$CLARITY_USER`:$CLARITY_PASSWORD@$POSTGRES_HOST`:$POSTGRES_PORT/$CLARITY_DB" -ForegroundColor Yellow
Write-Host ""
Write-Host "Próximos passos:" -ForegroundColor Green
Write-Host "1. Atualize .env com a string de conexão acima" -ForegroundColor White
Write-Host "2. Execute a app: python -m uvicorn app.main:app --reload" -ForegroundColor White
Write-Host ""
