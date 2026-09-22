---
name: sgdic-architecture
description: Arquitectura MVT del proyecto ProyectoASI/SGDIC (Django 4.2). Usa al modificar rutas, models, views, templates o al necesitar saber qué app hace qué, roles RBAC o estructura de carpetas.
---

# Arquitectura SGDIC (ProyectoASI)

Sistema institucional Django 4.2 (MVT), Python 3.12. RF-01…RF-56 y RN-01…RN-12.

## Stack
- Django 4.2 LTS, SQLite (dev) / PostgreSQL vía `DATABASE_URL` (prod), WhiteNoise (estáticos).
- Frontend: templates Django + Bootstrap 5.3 + Bootstrap Icons + Chart.js (CDN). **Sin SPA**: formularios POST + `redirect`.
- Usuario propio `usuario.Usuario(AbstractUser)` con campo `rol`. RBAC en `comun/mixins.py`.

## Apps y montaje de URLs (raíz `sgdic/urls.py`)
| App | Prefijo | Modelos principales |
|---|---|---|
| `usuario` | `/cuenta/` | `Usuario` (rol, semestre, promedio) |
| `materias` | `/materias/` | `Materia`, `VersionMateria`, `SolicitudMateria`, `MallaCurricular` |
| `cupos` | `/cupos/` | `OfertaCupo`, `SolicitudCupo`, `Inscripcion`, `Preinscripcion`, `PreferenciaPreinscripcion` |
| `mensajes` | `/mensajes/` | `Hilo`, `Mensaje` |
| `evaluaciones` | `/evaluaciones/` | `Sesion`, `Falta`, `ResumenInasistencia`, `PeriodoEvaluacion`, `InvitacionEvaluacion`, `RespuestaEvaluacion` |
| `quejas` | `/quejas/` | `CategoriaQueja`, `Queja`, `Seguimiento` |
| `reportes` | `/reportes/` | `PlantillaReporte`, `ReporteGenerado`, `ProgramacionReporte` |
| `analitica` | `/analitica/` | `NecesidadDetectada`, `PrediccionDemanda` |
| `comun` | — (transversal) | `AuditoriaLog`, `Notificacion` |

Raíz también monta: `/` → `dashboard`, `/notificaciones/`, `/admin/`.

## Roles RBAC (`comun/mixins.py`)
`ROLES_STAFF = ("SECRETARIA", "DEPARTAMENTO", "ADMIN")`. Atajos en `Usuario`: `es_estudiante`, `es_docente`, `es_secretaria`, `es_departamento`, `es_staff_sgdic`.
- `requiere_rol(*roles)` — decorador FBV (ADMIN siempre pasa).
- `MixinRol` (CBV, atributo `roles_permitidos`), `MixinStaff(MixinRol)` = staff.
- `rol_usuario(user)`, `es_staff(user)`.

## Dashboards por rol (`sgdic/views.py::dashboard`)
`ESTUDIANTE` → `dashboard_estudiante.html`; `DOCENTE` → `dashboard_docente.html`; `SECRETARIA|DEPARTAMENTO|ADMIN` → `dashboard_admin.html`; default `dashboard.html`. Contexto: `rol`, `es_staff`, `kpis` (de `comun/kpi.py::tablero_kpis`).

## Capas
- **Templates** en `templates/` (global, `DIRS`), base `base.html` + `comun/_menu_lateral.html`.
- **Vistas** en `<app>/views.py`: FBV con `@login_required`/`@requiere_rol` o CBV `ListView` + `MixinRol`.
- **Forms** en `<app>/forms.py` (ModelForm / Form con `class="form-control"`).
- **Servicios** (`reportes/servicios.py`, `analitica/servicios.py`): lógica de negocio pura.
- **KPIs**: `comun/kpi.py`. **Middleware**: `comun/middleware.py::ConfiguracionSGDIC` inyecta `request.sgdic_config` (settings `SGDIC_*`).
- **Auditoría / notificaciones**: `AuditoriaLog.registrar(...)`, `Notificacion.enviar(...)` en `comun/models.py`.

## Comandos clave
- `python manage.py runserver`, `check`, `makemigrations <app>`, `migrate`, `test`, `collectstatic`.
- Seed demo: `python manage.py datos_demo`.
