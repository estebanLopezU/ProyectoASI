# =====================================================================
# deploy.ps1 - Pipeline automático de despliegue SGDIC
#   1) Tests  2) Commit + push  3) vercel --prod  4) Verificación en prod
#
# Uso:
#   .\deploy.ps1                        # todo el pipeline
#   .\deploy.ps1 -Mensaje "fix x"       # commit con mensaje propio
#   .\deploy.ps1 -SoloDeploy            # solo despliegue (sin tests/push)
#   .\deploy.ps1 -SinTests              # omite la suite
#
# Nota: vercel --prod se cuelga si corre en la terminal del bot, por eso
#       se lanza con Start-Process y se espera leyendo el log.
# =====================================================================
param(
    [string]$Mensaje = "",
    [switch]$SinTests,
    [switch]$SoloDeploy
)

$raiz = $PSScriptRoot
$vercel = "C:\Users\esteb\AppData\Roaming\npm\vercel.cmd"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$logErr = Join-Path $raiz "vercel-deploy-err.log"
$logOut = Join-Path $raiz "vercel-deploy-last.log"
$urlProd = "https://proyectoasi-sgdic.vercel.app"

function Paso($t)  { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Ok($t)    { Write-Host "OK  $t" -ForegroundColor Green }
function Fallo($t) { Write-Host "FALLO  $t" -ForegroundColor Red; exit 1 }

Push-Location $raiz

# ---- 1) Tests -------------------------------------------------------
if (-not $SinTests -and -not $SoloDeploy) {
    Paso "TESTS"
    & $python manage.py test 2>&1 | Tee-Object -Variable salida | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $salida | Select-Object -Last 20
        Fallo "La suite de pruebas fallo. No se despliega."
    }
    Ok "Suite de pruebas OK"
}

# ---- 2) Commit + push ----------------------------------------------
if (-not $SoloDeploy) {
    Paso "GIT"
    git add -A
    $sucios = git status --porcelain
    if ($sucios) {
        if (-not $Mensaje) {
            $Mensaje = "Despliegue automatico " + (Get-Date -Format "yyyy-MM-dd HH:mm")
        }
        git -c core.quotepath=false commit -m $Mensaje | Out-Null
        Ok "Commit: $Mensaje"
    } else {
        Ok "Sin cambios que commitear"
    }

    $adelantado = git rev-list --count "origin/main..HEAD"
    if ($adelantado -gt 0) {
        # Evita que el hook pre-push lance un segundo deploy: este script
        # ya se encarga de desplegar en el paso 3.
        $env:SGDIC_DEPLOY_AUTO = "0"
        git push origin main 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Fallo "git push fallo." }
        Ok "Push a origin/main ($adelantado commit(s))"
    } else {
        Ok "origin/main ya esta al dia"
    }
}

# ---- 3) Deploy a Vercel --------------------------------------------
Paso "DEPLOY VERCEL (produccion)"
Remove-Item $logErr, $logOut -ErrorAction SilentlyContinue
Start-Process -FilePath $vercel `
    -ArgumentList "deploy", "--prod", "--yes" `
    -WorkingDirectory $raiz `
    -RedirectStandardError $logErr `
    -RedirectStandardOutput $logOut `
    -NoNewWindow | Out-Null

$fin = (Get-Date).AddSeconds(240)
$estado = "timeout"
do {
    Start-Sleep -Seconds 5
    $t = ""
    if (Test-Path $logErr) { $t = Get-Content $logErr -Raw -ErrorAction SilentlyContinue }
    if (-not $t) { $t = "" }
    if ($t -match "Ready in")           { $estado = "ready" }
    elseif ($t -match "(?m)^Error:")    { $estado = "error" }
} while ($estado -eq "timeout" -and (Get-Date) -lt $fin)

if (Test-Path $logErr) {
    Get-Content $logErr | Where-Object { $_ -match "Ready in|Error|Aliased|https://" } |
        ForEach-Object { Write-Host "  $_" }
}

switch ($estado) {
    "ready"   { Ok "Deploy listo" }
    "error"   { Fallo "Vercel devolvio un error. Revisa $logErr" }
    default   { Fallo "Tiempo de espera agotado (240s). Revisa $logErr" }
}

# ---- 4) Verificacion en produccion ---------------------------------
Paso "VERIFICACION EN PRODUCCION"
try {
    $r = Invoke-WebRequest -Uri "$urlProd/cuenta/login/" -UseBasicParsing -TimeoutSec 30
    if ($r.StatusCode -ne 200) { Fallo "Login devolvio HTTP $($r.StatusCode)" }
    Ok "Login HTTP 200"

    $m = [regex]::Match($r.Content, 'href="([^"]*sgdic[^"]*\.css[^"]*)"')
    if (-not $m.Success) { Fallo "No encontre el CSS en la pagina." }
    $uCss = $m.Groups[1].Value
    if ($uCss.StartsWith("/")) { $uCss = $urlProd + $uCss }
    $css = (Invoke-WebRequest -Uri $uCss -UseBasicParsing -TimeoutSec 30).Content

    if ($css.Contains(".anuncios-dashboard .cartelera-banner")) {
        Ok "CSS actualizado: cartelera compacta del Tablero desplegada ($uCss)"
    } else {
        Fallo "El CSS en prod no trae la regla nueva. Cache vieja?"
    }
    $alias = if (Test-Path $logOut) { (Get-Content $logOut | Select-Object -Last 1) } else { "" }
    Ok "Produccion: $urlProd"
    if ($alias) { Write-Host "  alias: $alias" }
} catch {
    Fallo "Verificacion fallida: $($_.Exception.Message)"
}

Pop-Location
Write-Host "`nDESPLEGUE COMPLETADO" -ForegroundColor Green
exit 0