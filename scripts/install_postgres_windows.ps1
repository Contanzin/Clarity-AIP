# ============================================================================
# CLARITY A.I.P - Bootstrap do ambiente Windows (PostgreSQL 17 + pgvector)
# ============================================================================
# Rode este script em um PowerShell como Administrador (botão direito >
# "Executar como Administrador"), a partir da raiz do projeto:
#
#   .\scripts\install_postgres_windows.ps1
#
# O que ele faz:
#   1. Instala o Git (necessário para baixar o código-fonte do pgvector)
#   2. Instala o PostgreSQL 17 (instalador oficial EDB, via winget)
#   3. Instala o Visual Studio Build Tools com o workload C++
#      (necessário para compilar a extensão pgvector no Windows)
#   4. Compila e instala a extensão pgvector a partir do código-fonte oficial
#
# Depois de rodar este script, volte ao Claude Code / terminal normal (sem
# admin) e siga com o setup do banco (db/setup.ps1).
# ============================================================================

$ErrorActionPreference = "Stop"

$SuperPassword = "clarity_dev_superuser"
$PgVersion = "17"
$PgVectorTag = "v0.8.1"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "ERRO: este script precisa ser rodado como Administrador." -ForegroundColor Red
    exit 1
}

function Install-IfMissing {
    param([string]$WingetId, [string]$OverrideArgs)

    $already = winget list --id $WingetId -e 2>$null | Select-String -SimpleMatch $WingetId
    if ($already) {
        Write-Host "      $WingetId já está instalado, pulando." -ForegroundColor Yellow
        return
    }

    if ($OverrideArgs) {
        winget install --id $WingetId -e --silent --accept-package-agreements --accept-source-agreements --override $OverrideArgs
    } else {
        winget install --id $WingetId -e --silent --accept-package-agreements --accept-source-agreements
    }
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar $WingetId (código $LASTEXITCODE). Verifique a saída acima." }
}

Write-Host "[1/4] Instalando Git..." -ForegroundColor Cyan
Install-IfMissing -WingetId "Git.Git"

Write-Host "[2/4] Instalando PostgreSQL $PgVersion (senha do superusuário: $SuperPassword)..." -ForegroundColor Cyan
Install-IfMissing -WingetId "PostgreSQL.PostgreSQL.$PgVersion" `
    -OverrideArgs "--mode unattended --unattendedmodeui minimal --superpassword $SuperPassword --serverport 5432"

Write-Host "[3/4] Instalando Visual Studio Build Tools (workload C++, pode demorar vários minutos)..." -ForegroundColor Cyan
Install-IfMissing -WingetId "Microsoft.VisualStudio.2022.BuildTools" `
    -OverrideArgs "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"

Write-Host "[4/4] Compilando a extensão pgvector ($PgVectorTag) a partir do código-fonte..." -ForegroundColor Cyan

$vcvars = Get-ChildItem "C:\Program Files\Microsoft Visual Studio\2022","C:\Program Files (x86)\Microsoft Visual Studio\2022" `
    -Recurse -Filter "vcvars64.bat" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $vcvars) { throw "vcvars64.bat não encontrado. O Build Tools instalou corretamente?" }

$gitExe = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitExe) {
    # git recém-instalado pode não estar no PATH desta sessão ainda
    $gitCandidate = "C:\Program Files\Git\cmd\git.exe"
    if (Test-Path $gitCandidate) { $env:PATH += ";C:\Program Files\Git\cmd" }
}

$srcDir = "$env:TEMP\pgvector_build"
if (Test-Path $srcDir) { Remove-Item -Recurse -Force $srcDir }
git clone --branch $PgVectorTag --depth 1 https://github.com/pgvector/pgvector.git $srcDir
if ($LASTEXITCODE -ne 0) { throw "Falha ao clonar o repositório do pgvector." }

# Usamos um .bat temporário (em vez de "cmd /c cmd1 && cmd2 && ...") porque em
# uma linha só o %PATH% é expandido ANTES do vcvars64.bat rodar, apagando o
# PATH que ele configura (é por isso que "nmake" não era encontrado). Um .bat
# processa linha a linha, então cada %VAR% é resolvido no momento certo.
$buildBat = "$env:TEMP\pgvector_build.bat"
@"
@echo off
call "$($vcvars.FullName)"
if errorlevel 1 exit /b 1
set "PGROOT=C:\Program Files\PostgreSQL\$PgVersion"
set "PATH=%PATH%;%PGROOT%\bin"
cd /d "$srcDir"
nmake /F Makefile.win
if errorlevel 1 exit /b 1
nmake /F Makefile.win install
if errorlevel 1 exit /b 1
"@ | Set-Content -Path $buildBat -Encoding ascii

cmd /c "`"$buildBat`""
if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar/instalar o pgvector. Verifique a saída acima." }
Remove-Item $buildBat -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Setup do Windows concluido!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Superusuario do Postgres: postgres"
Write-Host "Senha do superusuario:    $SuperPassword"
Write-Host ""
Write-Host "Proximo passo: volte ao terminal normal (sem admin) e rode db\setup.ps1" -ForegroundColor Cyan
