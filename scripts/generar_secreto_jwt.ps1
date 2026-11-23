# generar_secreto_jwt.ps1 - Genera el secreto JWT compartido Monitor <-> CMM.
#
# Crea 48 bytes aleatorios (64 caracteres base64url) y los escribe en:
#   backend\.env de este repo             -> CMM_JWT_SECRET_KEY
#   ..\sena-dev-2026-backend\.env (CMM)   -> JWT_SECRET_KEY
# Reemplaza la línea si ya existe o la agrega al final. El valor nunca se
# muestra en pantalla. Después reinicia los dos backends (.\dev.ps1 restart)
# y vuelve a iniciar sesión: los tokens firmados con el secreto viejo dejan
# de servir.
#
# Uso:
#   powershell -File scripts\generar_secreto_jwt.ps1
#   powershell -File scripts\generar_secreto_jwt.ps1 -CmmEnv D:\ruta\al\.env

param(
    [string]$CmmEnv = (Join-Path $PSScriptRoot "..\..\sena-dev-2026-backend\.env")
)

$ErrorActionPreference = "Stop"
$MonitorEnv = Join-Path $PSScriptRoot "..\backend\.env"

$bytes = New-Object byte[] 48
# Create().GetBytes sirve en Windows PowerShell 5.1 y en PowerShell 7 (Fill solo en 7).
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
$secret = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")

function Set-EnvValue([string]$Path, [string]$Name, [string]$Value) {
    if (-not (Test-Path $Path)) {
        throw "No existe $Path"
    }
    $lines = [System.Collections.Generic.List[string]](Get-Content -LiteralPath $Path -Encoding UTF8)
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$Name\s*=") {
            $lines[$i] = "$Name=$Value"
            $found = $true
        }
    }
    if (-not $found) { $lines.Add("$Name=$Value") }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines((Resolve-Path $Path).Path, $lines, $utf8)
    Write-Host "  $Name actualizado en $((Resolve-Path $Path).Path)"
}

Write-Host "Secreto JWT nuevo ($($secret.Length) caracteres, no se muestra):"
Set-EnvValue $MonitorEnv "CMM_JWT_SECRET_KEY" $secret
Set-EnvValue $CmmEnv "JWT_SECRET_KEY" $secret
Write-Host "Listo. Reinicia los backends con .\dev.ps1 restart y vuelve a iniciar sesión."
