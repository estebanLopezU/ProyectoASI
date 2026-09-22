---
name: template-ui-patterns
description: Patrones de UI de ProyectoASI/SGDIC (base.html, dashboards, tarjetas KPI, tablas, formularios, mensajes, iconos Bootstrap). Usa al crear o editar templates para que las pantallas sean consistentes.
---

# Patrones de plantilla y UI

## Estructura base
```django
{% extends "base.html" %}
{% block titulo %}Título de la página{% endblock %}
{% block contenido %}
  <h3 class="mb-3"><i class="bi bi-icono me-2"></i>Título</h3>
  ...contenido...
{% endblock %}
{% block scripts %}{% endblock %}   {# opcional #}
```
- `base.html` ya carga Bootstrap 5.3, Bootstrap Icons y `sgdic.css`; **no** incluir CDNs extra.
- Mensajes flash (`messages`) los pinta `base.html`; solo usar `messages.success/error/info`.

## Componentes reutilizables
- **Tarjeta KPI**:
  ```html
  <div class="card tarjeta-kpi h-100"><div class="card-body">
    <h6 class="text-muted">Etiqueta</h6>
    <p class="display-6 mb-0">{{ valor }}</p>
  </div></div>
  ```
- **Tabla** con `table table-hover tabla-compacta align-middle`, cabecera `table-light`, estado vacío `{% empty %}`.
- **Formulario**: `form-control`/`form-select` en los widgets (ver `forms.py`); botones `btn btn-primary` / `btn btn-sm btn-outline-secondary` para "Volver".
- **Accesos rápidos**: `list-group list-group-flush` con `list-group-item-action`.

## Convenciones
- Iconos: `bi bi-*` (Bootstrap Icons).
- Acentos de color: variables CSS `--sgdic-primario`, `--sgdic-acento` (no colores hardcodeados salvo semáforo).
- Responsive: usar clases Grid Bootstrap (`row g-3`, `col-md-3`); tablas en `.table-responsive`.
- Estado vacío siempre visible (`{% empty %}` o `{% if lista %}...{% else %}...`).
- No duplicar bloques de layout: si se repite en >2 pantallas, crear `{% include "comun/_....html" %}` en `templates/comun/`.
