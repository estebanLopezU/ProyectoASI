---
name: query-optimization
description: ORM eficiente en ProyectoASI/SGDIC (select_related, prefetch_related, only/defer, evitar N+1, aggregate). Usa al escribir consultas en vistas o helpers para no degradar el rendimiento.
---

# Consultas ORM eficientes

## Regla anti N+1
Nunca acceder a `obj.relacion.campo` dentro de un bucle sobre una lista sin precarga.

```python
# MAL: N+1
for inscripcion in Inscripcion.objects.all():
    print(inscripcion.oferta.materia.nombre)

# BIEN
qs = Inscripcion.objects.select_related("oferta__materia").all()
```

## Qué usar
| Situación | Uso |
|---|---|
| FK o OneToOne (`oferta`, `materia`, `estudiante`) | `select_related("oferta__materia")` |
| M2M o reverse FK (`docentes`, `versiones`, `notificaciones`) | `prefetch_related("materia__docentes")` |
| Solo unas pocas columnas | `.only("codigo", "nombre")` o `.defer(...)` |
| Filtrar por relacionados | `.filter(oferta__materia=...)` (join en SQL) |
| Conteos/exposiciones | `.aggregate(Sum(...))`, `.count()` en SQL, no `len(qs)` |
| Listados paginados (ListView) | `select_related`/`prefetch_related` en `get_queryset` |

## En el proyecto
- `ListView.get_queryset` debe traer ya las relaciones que usará el template (`preinscripcion`, `panel`, etc.).
- Los `@property` que hacen consultas (ej. `estado_derivado`) se llaman **por fila**; si se usan en bucles grandes, precalcular con un `prefetch_related` o anotación.
- Evitar consultas dentro de `for` en templates: pasar el dato calculado desde la vista.

## Comprobación
En desarrollo, instalar `django-debug-toolbar` o revisar `connection.queries` solo si se sospecha de N+1; no dejarlo en producción.
