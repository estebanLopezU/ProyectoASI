---
name: git-workflow
description: Flujo de Git y convención de commits en ProyectoASI/SGDIC (estado limpio, no commitear temporales, orden push vs deploy Vercel). Usa antes de commit, push o despliegue.
---

# Flujo de Git

## Antes de commit
```powershell
git status --short --branch
git diff --check          # sin problemas de whitespace
```
- Working tree **limpio** salvo los cambios de la tarea.
- **No commitear** archivos temporales ni de entorno: `_*.*` (logs, txt), `.venv/`, `__pycache__/`, `db.sqlite3`, `.vercel/`, `*.pyc`.

## Orden recomendado
1. Validar (ver `verification-deploy`): `compileall` → `check` → `makemigrations --check` → `test`.
2. `git add -A` (o rutas concretas si hay temporales).
3. `git commit -m "<tipo>: <qué y por qué>"`.
4. `git push origin main`.
5. Desplegar en Vercel (después del push, nunca antes).

## Mensajes de commit
- Formato: `tipo: descripción` en inglés o español, una línea clara.
- Tipos usados: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`.
- Ejemplos del repo: `feat: Agregar seleccion de grupos en preinscripcion`.

## Push vs deploy
- **Push** → actualiza `origin/main`.
- **Vercel** → deploy separado (`vercel deploy --prod --force`); el push **no** despliega solo.
- Tras desplegar: `git log -1 --oneline` y `git status` deben coincidir con `origin/main` y árbol limpio.
