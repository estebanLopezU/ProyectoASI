---
name: error-messages-user
description: Cómo redactar mensajes al usuario y códigos de regla (RN-xx) en ProyectoASI/SGDIC (messages.success/error/info, alertas, español). Usa al añadir feedback en vistas o templates para mantener tono consistente.
---

# Mensajes al usuario y reglas de negocio

## Dónde
- **Flash** (tras una acción): `messages.success(request, "...")`, `messages.error(...)`, `messages.info(...)`, `messages.warning(...)`. Los pinta `base.html`.
- **Inline** (en la página): `alert alert-info|success|warning|danger` dentro del template.
- **Notificación persistente**: `Notificacion.enviar(...)` (bandeja + correo opcional).

## Tono y formato
- **Español**, trato de usted, frases cortas y en positivo cuando sea posible.
- Empezar con el resultado: *"Malla curricular actualizada."*, no *"Se actualizó correctamente la..."*.
- Si es error, decir **qué pasó** y **qué hacer**: *"Revise los datos del formulario."*.
- Referenciar la **regla** entre paréntesis cuando aplique: *"(RN-01)"*, *"(RN-13)"*, *"(RF-15)"*.
- No exponer detalles internos (tracebacks, SQL, claves).

## Ejemplos del proyecto
```python
messages.success(request, "Preinscripción enviada. Quedó en revisión.")   # éxito
messages.error(request, "Debe completar el mínimo de 3 materias (RN-13).") # error + regla
messages.info(request, "Solo los estudiantes pueden preinscribirse.")      # rol/permiso
```

## En template
```django
<div class="alert alert-warning">
  <strong>Alerta de prerrequisitos (RN-01):</strong>
  <ul class="mb-0 small"><li>...</li></ul>
</div>
```

## Niveles de `Notificacion`
`INFO` (default) · `WARN` (advertencia) · `CRIT` (crítica). Usar `WARN`/`CRIT` solo cuando el usuario deba actuar.
