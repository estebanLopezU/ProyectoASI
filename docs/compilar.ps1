# =====================================================================
#  Script de compilacion de la documentacion LaTeX
#  Uso:  powershell -ExecutionPolicy Bypass -File docs/compilar.ps1
#  Genera main.pdf con pdfLaTeX (MiKTeX) en tres pasadas para resolver
#  indice, listas y referencias cruzadas.
# =====================================================================

$ErrorActionPreference = 'Continue'
$docsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $docsDir) { $docsDir = (Get-Location).Path }
Set-Location $docsDir

Write-Host '=== Compilando documentacion LaTeX (pdfLaTeX) ===' -ForegroundColor Cyan

foreach ($pass in 1..3) {
    Write-Host "--- Pasada $pass de 3 ---" -ForegroundColor Yellow
    & pdflatex -interaction=nonstopmode main.tex | Out-Null
}

# Reporte final
if (Test-Path 'main.pdf') {
    $pdf = Get-Item 'main.pdf'
    Write-Host ''
    Write-Host '=== Compilacion exitosa ===' -ForegroundColor Green
    Write-Host ("PDF generado: {0} ({1:N0} bytes)" -f $pdf.FullName, $pdf.Length)
}
else {
    Write-Host 'No se genero el PDF. Revise main.log' -ForegroundColor Red
}

# Resumen de errores y referencias indefinidas del log
if (Test-Path 'main.log') {
    $errores = (Select-String -Path 'main.log' -Pattern '^!' | Measure-Object).Count
    $refs = (Select-String -Path 'main.log' -Pattern 'Reference.*undefined' | Measure-Object).Count
    Write-Host ("Errores LaTeX       : {0}" -f $errores)
    Write-Host ("Referencias rotas   : {0}" -f $refs)
}
