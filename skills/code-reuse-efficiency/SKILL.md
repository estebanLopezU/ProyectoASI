---
name: code-reuse-efficiency
description: Cómo actuar como ingeniero de software en ProyectoASI/SGDIC ahorrando tokens y evitando duplicación de código, archivos o lógica. Usa en TODA tarea para decidir qué leer, qué reutilizar y qué NO crear.
---

# Ingeniería con ahorro de tokens y sin duplicación

## Regla de oro: buscar ANTES de crear
1. **No reescribas lo que ya existe.** Antes de crear un archivo, modelo, helper o template, **busca** si ya hay uno equivalente:
   - Modelos/helpers: `search_codebase` con el nombre o `grep` de la lógica.
   - Rutas: revisar `<app>/urls.py` y `sgdic/urls.py`.
   - Templates: `Get-ChildItem templates -Recurse -Filter *.html`.
   - Estilos: `static/css/sgdic.css` antes de agregar CSS nuevo.
2. **Un solo archivo por responsabilidad.** No dupliques `views.py`, `tests.py` ni plantillas con nombres casi iguales (`_tmp`, `_orig`, `_copia`). Si hay un temporal (`_*.py`, `_*.txt`), borrarlo, no versionarlo.

## Ahorro de tokens (carga selectiva)
- Los skills se cargan **por `description`**: solo lee el skill relevante a la tarea actual (arquitectura / convenciones / verificación / playbook). No leas los 4 de corrido.
- **No releas archivos enteros** si ya los conoces de un skill; el skill resume la estructura. Usa `read_files` con `start_line/end_line` para rangos acotados.
- **No reselecciones masivos** de modelos/views tras cada edición; confía en el resumen del skill y solo relee lo que cambió.
- Evita `compileall`/`check` sobre apps no tocadas.

## Reutilizar (DRY) antes que duplicar
| Necesidad | Reutilizar (NO crear) |
|---|---|
| Control de acceso por rol | `requiere_rol(...)`, `MixinRol`, `MixinStaff`, `rol_usuario`, `es_staff` de `comun/mixins.py` |
| KPI de tablero | función en `comun/kpi.py` + `tablero_kpis` |
| Auditoría | `AuditoriaLog.registrar(...)` de `comun/models.py` |
| Notificación | `Notificacion.enviar(...)` de `comun/models.py` |
| Config de negocio | `request.sgdic_config` (middleware `ConfiguracionSGDIC`) |
| Layout, navbar, sidebar, mensajes | `templates/base.html` + `comun/_menu_lateral.html` (nunca re-copiar) |
| Estilos / colores / botones | clases existentes en `sgdic.css` + variables `--sgdic-*` |
| Estados / choices | `class Estado(TextChoices)` dentro del modelo, no constantes sueltas |
| Cálculos de presentación | `@property` en el modelo, no lógica repetida en templates |
| Exportación / predicción | `servicios.py` de `reportes`/`analitica` |

## Señales de duplicación → corrige
- Dos `def` con el mismo nombre o casi igual en distintas apps.
- Dos templates con el mismo bloque de HTML (extrae a `{% include %}` o a `base.html`).
- Mismo `path("...")` en dos `urls.py`.
- Mismo campo/método copiado en dos modelos (¿va en una app base o en `comun`?).
- Tests idénticos con nombres distintos.

## Flujo eficiente por tarea
1. Definir el alcance (1 sola cosa por turno).
2. Cargar **el skill que corresponda** + rango acotado del archivo a tocar.
3. Reutilizar de la tabla anterior; solo crear lo realmente nuevo.
4. Editar con `editor` (cambios quirúrgicos, no reescribir archivos enteros).
5. Validar con el skill `verification-deploy` (check, test, git).
6. Al final, resumir qué se cambió (evita releer todo para verificar).
