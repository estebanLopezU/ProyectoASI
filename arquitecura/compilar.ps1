# =====================================================================
#  Compilacion de la Documentacion Tecnica de Arquitectura (SGDIC)
#  Uso:  powershell -ExecutionPolicy Bypass -File compilar.ps1
# =====================================================================

$ErrorActionPreference = 'Continue'

# Carpeta raiz del script (aunque se invoque desde otro directorio)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
Set-Location $scriptDir

$buildDir = Join-Path $scriptDir 'build'
if (-not (Test-Path $buildDir)) { New-Item -ItemType Directory -Path $buildDir | Out-Null }

$jobName = 'main'
$passes  = 3

Write-Host ''
Write-Host '=== Compilando documentacion tecnica de arquitectura ===' -ForegroundColor Cyan

for ($i = 1; $i -le $passes; $i++) {
    Write-Host ("  Pasada {0} de {1} ..." -f $i, $passes) -ForegroundColor Gray
    & pdflatex -interaction=nonstopmode -halt-on-error -jobname=$jobName "$jobName.tex" `
        | Out-File -Encoding utf8 (Join-Path $buildDir "compile_$i.log")
}

$logFile = Join-Path $scriptDir "$jobName.log"

Write-Host ''
Write-Host '=== Resultado ===' -ForegroundColor Cyan

if (Test-Path $logFile) {
    $errores = Select-String -Path $logFile -Pattern '^!' -ErrorAction SilentlyContinue
    $overfull = (Select-String -Path $logFile -Pattern 'Overfull \\hbox' -ErrorAction SilentlyContinue).Count

    Write-Host ("  Errores LaTeX             : {0}" -f @($errores).Count)
    Write-Host ("  Cajas desbordadas (hbox)  : {0}" -f $overfull)
} else {
    Write-Host '  No se genero main.log' -ForegroundColor Red
}

$pdf = Join-Path $scriptDir "$jobName.pdf"
if (Test-Path $pdf) {
    $info = Get-Item $pdf
    Write-Host ("  PDF generado              : {0}  ({1:N0} KB)" -f $info.Name, ($info.Length / 1KB)) -ForegroundColor Green
    Write-Host ("  Ruta                      : {0}" -f $info.FullName)
} else {
    Write-Host '  El PDF no se genero. Revise build\compile_*.log' -ForegroundColor Red
}

Write-Host ''