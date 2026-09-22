---
name: django-conventions
description: Patrones de código del proyecto ProyectoASI/SGDIC (Django). Usa al escribir o editar views, models, forms, templates o urls para replicar el estilo existente y evitar errores.
---

# Convenciones Django del proyecto

## Vistas (FBV y CBV)
- FBV siempre con `@login_required`; añadir `@requiere_rol("X", "Y")` si hay control de acceso. ADMIN siempre pasa.
- Guards al inicio de FBV: `if rol_usuario(request.user) not in (...): messages.error(...); return redirect(...)`.
- CBV de lista: `class XView(MixinRol, ListView)` con `template_name`, `context_object_name`, `roles_permitidos = (...)`.
- Mutaciones en POST: `if request.method == "POST": ...` con `transaction.atomic()` y `messages.success/error` + `redirect(...)` (patrón PRG).
- Lookup por `pk` con `get_object_or_404(Model, pk=pk)`.

## Modelos
- `verbose_name` en español en cada campo; `class Meta` con `ordering`, `verbose_name(_plural)`.
- Estados con `class Estado(models.TextChoices)`; default en el campo.
- Reglas de negocio transaccionales como métodos (`@transaction.atomic def aprobar(...)`).
- Propiedades `@property` para cálculos de presentación (`color`, `porcentaje`, `etiqueta_*`).
- Relaciones: `on_delete`, `related_name` explícito, `limit_choices_to={"rol": "DOCENTE"}` para M2M de usuarios.
- `created/updated` con `auto_now_add` / `auto_now`.

## Forms
- `ModelForm` con `Meta.fields` + `widgets` (`forms.TextInput(attrs={"class": "form-control"})`).
- `clean_<campo>` para validaciones; `help_texts` y `labels` en español.
- En `__init__`, `campo.widget.attrs.setdefault("class", "form-control")` para formularios `Form` puros.

## Templates
- `{% extends "base.html" %}`, bloques `titulo`, `contenido`, `scripts`.
- Bootstrap 5: `card`, `table table-hover tabla-compacta`, `btn btn-sm btn-primary`, badges, `alert alert-*`.
- Íconos Bootstrap Icons (`bi bi-*`).
- Enlaces con `{% url 'app:nombre' pk %}` (usar `app_name` en `urls.py`).
- Mensajes: el loop ya está en `base.html`; no repetir.

## URLs
- Cada app: `app_name = "montaje"`, `urlpatterns = [path("ruta/", views.vista, name="nombre")]`.
- Incluir en `sgdic/urls.py` con `path("prefijo/", include("app.urls"))`.

## Errores comunes a evitar
- Olvidar `app_name` → `{% url %}` falla.
- Olvidar `@login_required` o el guard de rol → 500/403.
- Comparar `estado` con string literal en vez de `Model.Estado.X`.
- Escribir `{% if %}` sin `{% endif %}` o `{% for %}` con `{% empty %}` mal cerrado en templates.
- Campo `unique` sin `default` en migración sobre tabla con datos.
