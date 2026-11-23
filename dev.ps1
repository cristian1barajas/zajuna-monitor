# dev.ps1 - Lanza los servidores de desarrollo del Zajuna Monitor:
#   API CMM (auth) -> Backend Monitor -> Frontend
# Las bases de datos se levantan manualmente (Docker aparte).
# Uso:
#   .\dev.ps1          Inicia los servidores (omite los que ya esten corriendo)
#   .\dev.ps1 stop     Detiene los servidores
#   .\dev.ps1 restart  Detiene y vuelve a iniciar

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

# --- Config ---
$BACKEND_PORT = 8000
$FRONTEND_PORT = 3000
$CMM_PORT = 8001
$CMM_ROOT = (Resolve-Path "$ROOT\..\sena-dev-2026-backend").Path
# La base CMM va en 5433 (el 5432 lo usa el Postgres de otro proyecto).
# Levantala manualmente antes: en sena-dev-2026-backend ->
#   $env:POSTGRES_PORT='5433'; docker compose up -d postgres
$CMM_DB_PORT = 5433
$CMM_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:$CMM_DB_PORT/sena_cmm"
$NVM_NODE = "$env:APPDATA\nvm\v22.9.0"

function Test-Port($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Stop-Servers {
    Write-Host ""
    Write-Host "Deteniendo servidores..." -ForegroundColor Yellow

    $stopped = 0
    foreach ($port in @($BACKEND_PORT, $FRONTEND_PORT, $CMM_PORT)) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($conns) {
            foreach ($conn in $conns) {
                $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
                if ($proc) {
                    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                    $stopped++
                }
            }
        }
    }

    if ($stopped -gt 0) {
        Write-Host "  $stopped proceso(s) detenido(s)." -ForegroundColor Green
    } else {
        Write-Host "  No habia servidores corriendo." -ForegroundColor DarkGray
    }
    Write-Host ""
}

# --- Comando: stop ---
if ($args.Count -gt 0 -and $args[0] -eq "stop") {
    Stop-Servers
    exit 0
}

# --- Comando: restart ---
if ($args.Count -gt 0 -and $args[0] -eq "restart") {
    Stop-Servers
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "=== Zajuna Monitor - Dev Server ===" -ForegroundColor Cyan
Write-Host ""

# Aviso (no bloqueante): sin la base CMM el login fallara
if (-not (Test-Port $CMM_DB_PORT)) {
    Write-Host "  ADVERTENCIA: no se detecta Postgres en el puerto $CMM_DB_PORT." -ForegroundColor Red
    Write-Host "  El login fallara hasta que levantes la base CMM:" -ForegroundColor Red
    Write-Host "    cd $CMM_ROOT" -ForegroundColor DarkGray
    Write-Host "    `$env:POSTGRES_PORT='5433'; docker compose up -d postgres" -ForegroundColor DarkGray
    Write-Host ""
}

# --- [1/3] API CMM (autenticacion) ---
if (Test-Port $CMM_PORT) {
    Write-Host "[1/3] API CMM ya esta corriendo en puerto $CMM_PORT (omitido)" -ForegroundColor DarkGray
} else {
    Write-Host "[1/3] Iniciando API CMM (auth) en puerto $CMM_PORT..." -ForegroundColor Yellow

    $cmmScript = @"
`$Host.UI.RawUI.WindowTitle = 'CMM API :$CMM_PORT'
Set-Location '$CMM_ROOT'
`$env:DATABASE_URL = '$CMM_DB_URL'
& '.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port $CMM_PORT
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmmScript -WindowStyle Normal
    Start-Sleep -Seconds 2
}

# --- [2/3] Backend Monitor ---
if (Test-Port $BACKEND_PORT) {
    Write-Host "[2/3] Backend ya esta corriendo en puerto $BACKEND_PORT (omitido)" -ForegroundColor DarkGray
} else {
    Write-Host "[2/3] Iniciando Backend (FastAPI) en puerto $BACKEND_PORT..." -ForegroundColor Yellow

    $backendScript = @"
`$Host.UI.RawUI.WindowTitle = 'Zajuna Backend :$BACKEND_PORT'
Set-Location '$ROOT\backend'
& '.venv\Scripts\python.exe' -m uvicorn src.api.server:app --reload --host 127.0.0.1 --port $BACKEND_PORT
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendScript -WindowStyle Normal
    Start-Sleep -Seconds 2
}

# --- [3/3] Frontend ---
if (Test-Port $FRONTEND_PORT) {
    Write-Host "[3/3] Frontend ya esta corriendo en puerto $FRONTEND_PORT (omitido)" -ForegroundColor DarkGray
} else {
    Write-Host "[3/3] Iniciando Frontend (Next.js) en puerto $FRONTEND_PORT..." -ForegroundColor Yellow

    $frontendScript = @"
`$Host.UI.RawUI.WindowTitle = 'Zajuna Frontend :$FRONTEND_PORT'
`$env:PATH = '$NVM_NODE;' + `$env:PATH
Set-Location '$ROOT\frontend'
npm run dev
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendScript -WindowStyle Normal
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "=== Listo ===" -ForegroundColor Green
Write-Host ""
Write-Host "  API CMM:  http://127.0.0.1:$CMM_PORT/docs" -ForegroundColor White
Write-Host "  Backend:  http://127.0.0.1:$BACKEND_PORT/docs" -ForegroundColor White
Write-Host "  Frontend: http://127.0.0.1:$FRONTEND_PORT" -ForegroundColor White
Write-Host ""
Write-Host "  Todos detectan cambios en codigo automaticamente (--reload / HMR)." -ForegroundColor DarkGray
Write-Host "  .\dev.ps1 stop       Detener servidores" -ForegroundColor DarkGray
Write-Host "  .\dev.ps1 restart    Reiniciar servidores" -ForegroundColor DarkGray
Write-Host ""
