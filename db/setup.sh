#!/usr/bin/env bash
# ============================================================================
# CLARITY A.I.P - SETUP DO BANCO DE DADOS
# ============================================================================
# Descrição: Script para criar o banco PostgreSQL, habilitar extensões,
#            e carregar o schema inicial.
#
# Uso:
#   bash db/setup.sh
#
# PRÉ-REQUISITOS:
#   - PostgreSQL instalado e rodando (localhost:5432)
#   - Variáveis de ambiente definidas:
#       POSTGRES_SUPERUSER (padrão: postgres) — usado só para criar o banco/usuário
#       POSTGRES_SUPERUSER_PASSWORD           — senha definida na instalação do Postgres
#       POSTGRES_USER / POSTGRES_PASSWORD     — usuário da aplicação a ser criado
#       POSTGRES_DB (padrão: clarity_aip)
# ============================================================================

set -e  # Sai ao primeiro erro

# Defaults
# Usuário da aplicação (o que a app usa em runtime) — captura ANTES de
# sobrescrever POSTGRES_USER/POSTGRES_PASSWORD com as credenciais do superusuário.
CLARITY_USER="${POSTGRES_USER:-clarity_user}"
CLARITY_PASSWORD="${POSTGRES_PASSWORD:-clarity_password}"
CLARITY_DB="${CLARITY_DB:-clarity_aip}"

# POSTGRES_USER (superusuário, usado para CONECTAR e criar o resto)
POSTGRES_USER="${POSTGRES_SUPERUSER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_SUPERUSER_PASSWORD:-}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

echo "=========================================="
echo "Clarity A.I.P - Setup do Banco de Dados"
echo "=========================================="
echo ""
echo "Conectando como: $POSTGRES_USER"
echo "Host: $POSTGRES_HOST:$POSTGRES_PORT"
echo "Banco a criar: $CLARITY_DB"
echo ""

# Export para psql usar
export PGPASSWORD="$POSTGRES_PASSWORD"

# 1. Criar banco de dados
echo "[1/4] Criando banco de dados '$CLARITY_DB'..."
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -tc \
  "SELECT 1 FROM pg_database WHERE datname = '$CLARITY_DB'" | grep -q 1 || \
  psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
    -c "CREATE DATABASE $CLARITY_DB;"
echo "✓ Banco criado ou já existe"

# 2. Criar usuário de aplicação (se não existir)
echo "[2/4] Criando usuário '$CLARITY_USER'..."
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$CLARITY_DB" -tc \
  "SELECT 1 FROM pg_user WHERE usename = '$CLARITY_USER'" | grep -q 1 || \
  psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$CLARITY_DB" \
    -c "CREATE USER $CLARITY_USER WITH PASSWORD '$CLARITY_PASSWORD';"
echo "✓ Usuário criado ou já existe"

# 3. Conceder permissões
echo "[3/4] Concedendo permissões..."
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$CLARITY_DB" \
  -c "GRANT ALL PRIVILEGES ON DATABASE $CLARITY_DB TO $CLARITY_USER;"
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$CLARITY_DB" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $CLARITY_USER;"
# Tabelas com SERIAL/BIGSERIAL criam sequências à parte — sem isso, INSERTs do
# usuário da app falham com "permission denied for sequence".
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$CLARITY_DB" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $CLARITY_USER;"
echo "✓ Permissões concedidas"

# 4. Executar schema
echo "[4/4] Executando schema SQL..."
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$CLARITY_DB" \
  -f db/01_init_schema.sql
echo "✓ Schema carregado"

echo ""
echo "=========================================="
echo "✅ Setup completo!"
echo "=========================================="
echo ""
echo "String de conexão para a app:"
echo "postgresql+asyncpg://$CLARITY_USER:$CLARITY_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$CLARITY_DB"
echo ""
