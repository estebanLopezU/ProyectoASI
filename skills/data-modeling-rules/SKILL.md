---
name: data-modeling-rules
description: Reglas para diseñar modelos Django en ProyectoASI/SGDIC (TextChoices, on_delete, related_name, verbose_name en español, propiedades vs campos, transaction.atomic). Usa al crear o modificar models.py para no romper migraciones ni convenciones.
---

# Modelado de datos (models.py)

## Campos y opciones
- `verbose_name` **en español** en todos los campos y modelos (`verbose_name`/`verbose_name_plural` en `Meta`).
- Estados/tipos → `class Estado(models.TextChoices)` con valor = clave mayúscula y etiqueta legible (ej. `VISTA = "VISTA", "Vista (ya cursada)"`).
- Todo FK/M2M lleva `related_name` explícito y `on_delete` pensado:
  - `CASCADE` si el hijo no existe sin el padre (ej. `MallaCurricular.materia`).
  - `SET_NULL` + `null=True, blank=True` si es auditoría/autoría (ej. `actualizado_por`, `autor`).
- `limit_choices_to={"rol": "ESTUDIANTE"}` cuando el FK es a un `Usuario` con rol específico.
- `default=` siempre en campos no nulos que se crean por código (evita `IntegrityError` y migraciones sucias).
- `unique_together` para pares lógicos (ej. `("estudiante", "materia")`).
- `db_index=True` en campos usados en filtros frecuentes (`estado`, fechas).

## Propiedades vs campos
- **Campo** = dato persistido y editable por el administrador.
- **`@property`** = valor derivado/calcado (no migrar). Ej.: `estado_derivado`, `color`, `publicada`, `cupos_disponibles`.
- No guardar en campo algo que ya se puede calcular (evita duplicidad de fuente de verdad).

## Transacciones
- Operaciones múltiples → `@transaction.atomic` o `with transaction.atomic():` (ej. `SolicitudMateria.aprobar`).
- Tras guardar, `save(update_fields=[...])` para tocar solo lo necesario.

## Notificación / auditoría
- Acciones críticas → `AuditoriaLog.registrar(request, ACCION, objeto, detalle)`.
- Avisos → `Notificacion.enviar(destinatario, titulo, cuerpo, url=..., nivel=..., correo=...)`.

## Siempre
1. Editar `models.py`.
2. `manage.py makemigrations <app>` y `manage.py migrate`.
3. Registrar en `<app>/admin.py` si es consultable/editable.
