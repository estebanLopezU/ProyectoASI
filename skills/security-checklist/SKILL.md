---
name: security-checklist
description: Lista de seguridad para vistas y formularios de ProyectoASI/SGDIC (CSRF, login_required, no exponer datos ajenos, PermissionDenied, validación). Usa al crear endpoints o formularios, antes del commit.
---

# Seguridad (checklist antes del commit)

- **CSRF**: todo `<form method="post">` lleva `{% csrf_token %}`. Nunca desactivar `CsrfViewMiddleware`.
- **Autenticación**: toda vista sensible con `@login_required` o `MixinRol`/`@requiere_rol` (el decorador ya exige sesión).
- **Autorización por objeto**: además del rol, verificar que el recurso pertenece al usuario:
  ```python
  if obj.estudiante_id != request.user.pk and not es_staff(request.user):
      raise PermissionDenied("No tiene acceso a este recurso.")
  ```
- **No confiar en el cliente**: nunca tomar `rol`, `id` de estudiante o estados desde `request.POST`/`GET` sin validar contra `request.user`.
- **Formularios**: usar `ModelForm`/`Form` con `clean_*`; no asignar `request.POST` directo al modelo.
- **Método**: mutaciones solo en `POST` (redirigir en `GET` para evitar CSRF vía enlace).
- **Exposición de datos**: en listados no filtrar solo en el template; filtrar en el `queryset`.
- **Archivos**: `FileField` con `upload_to` restringido; validar tipo/tamaño si se suben evidencias.
- **Config**: `DEBUG=False` en producción, `SECRET_KEY` fuera del repo, `ALLOWED_HOSTS` correcto.
- **Mensajes de error**: no verter `traceback`s al usuario en producción (`fail_silently` en correos).

## RBAC resumido
Ver skill `roles-rbac-guide` para elegir `@requiere_rol` vs `MixinRol` vs guard manual.
