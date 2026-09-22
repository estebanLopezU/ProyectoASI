---
name: performance-checklist
description: Checklist de rendimiento antes de producción en ProyectoASI/SGDIC (índices, consultas en bucle, collectstatic, tamaño de db.sqlite3/media). Usa al terminar una feature o antes de desplegar.
---

# Rendimiento antes de producción

## Consultas
- [ ] Sin N+1: `select_related`/`prefetch_related` en listados (ver `query-optimization`).
- [ ] Sin consultas dentro de `for` de template; precalcular en la vista.
- [ ] `count()`/`aggregate()` en SQL, no `len(qs)` en Python.
- [ ] Paginación en listados grandes (`paginate_by` en `ListView`).

## Índices
- [ ] `db_index=True` en columnas filtradas con frecuencia (`estado`, fechas, `periodo`).
- [ ] `unique_together` traducido a índice único real.
- [ ] Tras cambiar modelos: `makemigrations` + `migrate`.

## Estáticos y media
- [ ] `collectstatic` sin errores (`--noinput` en CI/producción).
- [ ] Imágenes/media optimizados; no subir `db.sqlite3` de demo al repo de prod.
- [ ] `DEBUG=False` en producción (no servir estáticos con `runserver`).

## Base de datos
- [ ] Migraciones aplicadas y `makemigrations --check` limpio.
- [ ] SQLite solo para desarrollo/demo; considerar Postgres si hay concurrencia real.

## Medición rápida
```powershell
.\.venv\Scripts\python.exe manage.py shell -c "from django.db import connection; print(len(connection.queries))"
```
(Solo con `DEBUG=True`; desactivar en producción.)
