---
name: verification-deploy
description: Checklist de validación, tests y despliegue (Vercel/Render) del proyecto ProyectoASI/SGDIC. Usa antes de hacer commit, al terminar una tarea o al desplegar a producción.
---

# Verificación y despliegue SGDIC

## Checklist de validación (ejecutar en `.venv`)
```powershell
cd c:\Users\esteb\OneDrive\Desktop\ProyectoASI
.\.venv\Scripts\python.exe -m compileall -q <apps modificadas>
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations <app> --check --dry-run   # sin cambios = OK
.\.venv\Scripts\python.exe manage.py test
git diff --check   # sin whitespace issues
```
- `check` → `System check identified no issues`.
- `makemigrations --check` → `No changes detected` (o aplicar `migrate` si hay).
- Tests centralizados en `sgdic/tests.py` (clase `BaseDatos` + `PruebasReglasCupo`, `PruebasAnalitica`, `PruebasQuejas`, `PruebasVistas`, `PruebasMallaCurricular`).

## Commit y push
```powershell
git status --short --branch
git add -A
git commit -m "Mensaje claro en inglés/español"
git push origin main
```
HEAD y `origin/main` deben coincidir; working tree limpio.

## Despliegue Vercel
- Proyecto vinculado: `proyectoasi-sgdic` (`.vercel/project.json`).
- Build: `vercel-build.sh` (o `build.sh`) → `pip install -r requirements.txt`, `collectstatic --no-input`, `migrate`.
- Deploy prod forzado: `vercel deploy --prod --force --yes`.
- Verificar: `vercel ls`, `vercel inspect <url>`, smoke test HTTP a `https://proyectoasi-sgdic.vercel.app/` (esperado `302` → `/cuenta/login/` o página de login con `200`).
- `settings.py` detecta `VERCEL=1` y copia `db.sqlite3` a `/tmp/sgdic.sqlite3` (filesystem de solo lectura).

## Despliegue Render (alternativa)
`render.yaml` + `build.sh` (collectstatic + migrate). `DATABASE_URL` inyectado por Render → PostgreSQL.

## Limpieza
No commitear archivos temporales (`_*.txt`, `_*.log`, `_*.ps1`). Están en `.gitignore`/`.vercelignore`.
