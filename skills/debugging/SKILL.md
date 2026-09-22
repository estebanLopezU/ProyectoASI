---
name: debugging
description: Diagnóstico rápido de errores del proyecto ProyectoASI/SGDIC (check, compileall, tracebacks, URL no resuelta, migraciones). Usa cuando algo falla al correr el servidor o los tests.
---

# Debugging rápido

## Orden de diagnóstico
```powershell
cd c:\Users\esteb\OneDrive\Desktop\ProyectoASI
.\.venv\Scripts\python.exe -m compileall -q <apps>   # errores de sintaxis
.\.venv\Scripts\python.exe manage.py check           # System check identified no issues
.\.venv\Scripts\python.exe manage.py test            # 0 fallos, 0 errores
```
Si el servidor no arranca, mirar el **primer** `Traceback` completo (no el final).

## Errores comunes y causa
| Síntoma | Causa probable |
|---|---|
| `NoReverseMatch` / URL no resuelta | Falta `path()` en `<app>/urls.py` o mal `name=` / `app_name` |
| `OperationalError: no such table` | Falta `migrate` tras crear modelo |
| `makemigrations` dice cambios siempre | Campo sin `default` o `null=True` inconsistente |
| `IndentationError` / `TemplateSyntaxError` | Espacios mezclados; `{% if %}` sin `{% endif %}` o `{% for %}` sin `{% endfor %}` |
| `ImportError` / `circular import` | Import local dentro de la función, no al inicio del módulo |
| `PermissionDenied` (403) inesperado | `@requiere_rol` o `MixinRol` con `roles_permitidos` que no incluye el rol |
| `FieldError` en template | Typo en `related_name` o atributo del contexto |

## Migraciones
```powershell
.\.venv\Scripts\python.exe manage.py makemigrations <app>   # generar
.\.venv\Scripts\python.exe manage.py migrate                # aplicar
.\.venv\Scripts\python.exe manage.py makemigrations <app> --check --dry-run   # debe decir No changes detected
```

## Traceback útil
Leer de arriba hacia abajo hasta la **primera** línea que apunta a un archivo del proyecto (`materias/views.py`, no site-packages).
