---
name: roles-rbac-guide
description: Guía de permisos RBAC por rol del proyecto ProyectoASI/SGDIC (SECRETARIA, DEPARTAMENTO, ADMIN, DOCENTE, ESTUDIANTE). Usa al proteger vistas, elegir decoradores o verificar quién puede ver/editar cada módulo.
---

# Permisos por rol (RBAC)

Fuente: `comun/mixins.py` (`rol_usuario`, `requiere_rol`, `MixinRol`, `MixinStaff`, `es_staff`, `ROLES_STAFF`).

## Roles
`ESTUDIANTE` · `DOCENTE` · `SECRETARIA` · `DEPARTAMENTO` · `ADMIN`
- `ROLES_STAFF = ("SECRETARIA", "DEPARTAMENTO", "ADMIN")` → "administrativo".
- `ADMIN` (o superuser) **siempre pasa** cualquier `requiere_rol` / `MixinRol`.

## Cuándo usar qué
| Situación | Mecanismo |
|---|---|
| Vista de función, rol fijo | `@requiere_rol("SECRETARIA", "DEPARTAMENTO", "ADMIN")` |
| CBV (ListView/DetailView) | `class V(MixinRol, ...)` + `roles_permitidos = (...)`, o `MixinStaff` |
| Guard manual con mensaje | `if rol_usuario(request.user) != "ESTUDIANTE": messages.error(...); return redirect(...)` |
| Comprobar staff | `es_staff(request.user)` |

## Acceso por módulo (resumen)
| Módulo | Quién |
|---|---|
| Preinscripción, horario, solicitudes de cupo | ESTUDIANTE |
| Proponer/editar materia, registrar asistencia | DOCENTE |
| Revisar solicitudes de materia | DEPARTAMENTO |
| Procesar cupos, listas de espera | SECRETARIA / DEPARTAMENTO / ADMIN |
| **Editar malla curricular** (`materias:malla_editar`) | solo SECRETARIA / DEPARTAMENTO / ADMIN |
| Ver malla (`materias:malla`) | propio (estudiante), docente de sus materias, o staff |
| Reportes, analítica, quejas (panel) | staff / según `requiere_rol` de cada vista |

## Plantilla de vista protegida
```python
@login_required
@requiere_rol("SECRETARIA", "DEPARTAMENTO", "ADMIN")
def mi_vista(request):
    ...
```

## En template
```django
{% if puede_editar %} ... {% endif %}          # contexto de la vista
{% if user.es_staff_sgdic %} ... {% endif %}    # atajo en modelo Usuario
```
