---
name: feature-playbook
description: Receta paso a paso para agregar una funcionalidad completa al proyecto ProyectoASI/SGDIC (modelo, migración, vista, URL, template, test). Usa cuando se pida crear o extender un módulo nuevo.
---

# Playbook: nueva funcionalidad

Ejemplo aplicado a "malla curricular" (funcionalidad ya existente, úsala como referencia).

## 1. Modelo
- Editar `<app>/models.py`: agregar campo o clase nueva con `verbose_name`, `Estado(TextChoices)`, `Meta`.
- Ej.: `MallaCurricular` en `materias/models.py` (FK estudiante+materia, `semestre`, `estado` manual con `""` = derivado).
- Registrar en `<app>/admin.py` si aplica (`@admin.register(Model)`).

## 2. Migración
```powershell
.\.venv\Scripts\python.exe manage.py makemigrations <app>
.\.venv\Scripts\python.exe manage.py migrate
```
Verificar con `makemigrations <app> --check --dry-run` → `No changes detected`.

## 3. Form (si hay entrada de datos)
- `<app>/forms.py`: `ModelForm` con `widgets` (`class="form-control"`/`form-select`), `labels`, `help_texts`, `clean_<campo>`.

## 4. Vista
- `<app>/views.py`: FBV `@login_required` (+ `@requiere_rol` si aplica) o CBV `MixinRol, ListView`.
- Guards de rol con `rol_usuario(request.user)`.
- Para operaciones: `transaction.atomic()`, `AuditoriaLog.registrar(...)`, `Notificacion.enviar(...)`, `messages` + `redirect`.

## 5. URL
- `<app>/urls.py`: `path("ruta/<int:pk>/", views.vista, name="nombre")`. El `app_name` ya existe.

## 6. Template
- Crear `templates/<app>/malla.html` (o la que corresponda): `{% extends "base.html" %}`, `{% block titulo %}` y `{% block contenido %}`, Bootstrap 5 + Icons, `{% url 'app:nombre' pk %}`.
- Enlazar en `templates/comun/_menu_lateral.html` dentro del bloque de rol correcto.
- Agregar tarjeta/ acceso en `dashboard_<rol>.html` si aplica.

## 7. KPI (opcional)
- Si alimenta el tablero: función en `comun/kpi.py` y exponerla en `tablero_kpis`; consumir en el dashboard.

## 8. CSS (si necesita estilo propio)
- Agregar a `static/css/sgdic.css` (tema sobre Bootstrap). Respetar variables `--sgdic-primario`, `--sgdic-acento`.

## 9. Tests
- Agregar clase en `sgdic/tests.py` heredando `BaseDatos`:
  - `test_estado_derivado...` (lógica de dominio)
  - `test_estudiante_...` (permisos: ve lo suyo, no edita)
  - `test_administrativo_...` (staff puede editar)
- Usar `self.login(...)` de `BaseDatos` y `reverse("app:nombre", args=[...])`.

## 10. Validar y desplegar
Seguir skill `verification-deploy`: compileall → check → makemigrations --check → test → commit/push → `vercel deploy --prod --force`.
