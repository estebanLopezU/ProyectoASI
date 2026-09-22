# SGDIC — Sistema de Gestión Departamental de Informática y Computación

Sistema web institucional para la gestión académica y administrativa de un departamento
de informática: ofertas de cupos, catálogo de materias, mensajería estudiante-docente,
control de inasistencias, evaluación docente anónima, gestión de quejas, reportes
exportables y analítica de decisión con predicción de demanda.

Implementa los requerimientos funcionales **RF-01 a RF-56** y las reglas de negocio
**RN-01 a RN-12** definidos en la documentación del proyecto (`docs/`, `arquitecura/`).

---

## 1. Stack tecnológico

| Componente        | Tecnología |
|-------------------|------------|
| Lenguaje          | Python 3.12 |
| Framework         | Django 4.2 LTS (patrón **MVT**: Model–View–Template) |
| Base de datos     | SQLite (desarrollo) / PostgreSQL (producción, vía variables de entorno) |
| Frontend          | Plantillas Django + Bootstrap 5.3 + Bootstrap Icons + Chart.js (CDN) |
| Autenticación     | `django.contrib.auth` con modelo de usuario propio (`usuario.Usuario`) y RBAC por roles |
| Correo            | Backend de consola para desarrollo (`django.core.mail.backends.console`) |
| Exportación       | CSV nativo · Excel con `openpyxl` (opcional) · PDF con `reportlab` (opcional) |
| Sin SPA           | Renderizado en servidor, flujos por formularios POST + redirección (arquitectura del documento técnico) |

> **Nota:** `openpyxl` y `reportlab` son dependencias *opcionales*: si no están instaladas,
> la descarga en esos formatos cae automáticamente a CSV sin romper la aplicación.

---

## 2. Arquitectura general

La arquitectura sigue el patrón MVT de Django en tres capas, tal como se definió en el
documento de arquitectura:

```
┌────────────────────────────────────────────────────────────────────┐
│  CAPA DE PRESENTACIÓN (Templates · T)                              │
│  templates/  →  base.html, dashboards por rol, plantillas por app  │
│  static/css/ →  sgdic.css (ajustes sobre Bootstrap 5)              │
│  Bootstrap 5 + Icons + Chart.js cargados por CDN                  │
└──────────────────────────▲─────────────────────────────────────────┘
                           │ contexto render()
┌──────────────────────────┴─────────────────────────────────────────┐
│  CAPA DE LÓGICA (Views · V) + rutas (URLconf)                      │
│  <app>/views.py   → funciones y ListView con control RBAC          │
│  <app>/urls.py    → rutas por app, incluidas desde sgdic/urls.py   │
│  <app>/forms.py   → validación de entrada                          │
│  <app>/servicios.py (reportes, analitica) → lógica de negocio pura │
│  comun/mixins.py  → decoradores de rol (requiere_rol, MixinRol)    │
│  comun/kpi.py     → cálculo de indicadores para los tableros       │
│  comun/middleware.py → inyecta request.sgdic_config en cada request│
└──────────────────────────▲─────────────────────────────────────────┘
                           │ ORM Django
┌──────────────────────────┴─────────────────────────────────────────┐
│  CAPA DE DATOS (Models · M)                                        │
│  <app>/models.py  → modelos ORM, reglas de negocio transaccionales │
│  <app>/migrations/→ versionado del esquema                         │
│  SQLite / PostgreSQL                                              │
│  media/           → evidencias de quejas, justificaciones, reportes│
└────────────────────────────────────────────────────────────────────┘
```

Principios aplicados:

- **Reglas de negocio dentro de los modelos**: las validaciones críticas
  (RN-01…RN-12) viven en métodos de los modelos (`SolicitudCupo.procesar()`,
  `Queja.escalar()`, `NecesidadDetectada.calcular_score()`, etc.), no en las vistas.
  Las vistas orquestan y los modelos garantizan invariantes con `transaction.atomic`.
- **Acoplamiento bajo entre apps**: cada app importa a `comun` (notificaciones,
  auditoría, roles) y usa referencias por string (`"materias.Materia"`,
  `settings.AUTH_USER_MODEL`) para evitar dependencias circulares.
- **Notificación como servicio común**: `Notificacion.enviar(destinatario, titulo,
  cuerpo, url, nivel, correo)` crea la notificación in-app y (opcionalmente) envía
  el correo; la usan cupos, evaluaciones, quejas, mensajes y analítica.
- **Auditoría transversal**: `AuditoriaLog.registrar(request, accion, objeto, detalle)`
  registra las operaciones críticas (radicar/gestionar quejas, generar/descargar
  reportes, aprobar solicitudes de materia).

---

## 3. Estructura de directorios

```
ProyectoASI/
├── manage.py                  # CLI de Django (runserver, migrate, test, ...)
├── requirements.txt           # Dependencias fijadas (Django 4.2.30 + opcionales)
├── db.sqlite3                 # Base de datos de desarrollo (con datos demo)
├── README.md                  # Este documento
│
├── sgdic/                     # ⚙️ Proyecto Django (configuración)
│   ├── settings.py            # Config global: apps, BD, reglas SGDIC_*, i18n
│   ├── urls.py                # Rutas raíz: incluye las 8 apps + dashboard
│   ├── views.py               # Dashboard por rol + bandeja de notificaciones
│   ├── tests.py               # 20 pruebas (RN críticas, RBAC, vistas, KPIs)
│   └── wsgi.py                # Punto de entrada WSGI para producción
│
├── comun/                     # 🧩 App transversal (no expone URLs)
│   ├── models.py              # AuditoriaLog, Notificacion + helper enviar()
│   ├── mixins.py              # RBAC: rol_usuario, requiere_rol, MixinRol, MixinStaff
│   ├── kpi.py                 # KPIs por rol (tablero_kpis) + kpi_* por módulo
│   ├── middleware.py          # request.sgdic_config (parámetros de negocio)
│   └── admin.py               # Administración de auditoría y notificaciones
│
├── usuario/                   # 👤 Autenticación, perfiles y RBAC (RF-01…03)
│   ├── models.py              # Usuario(AbstractUser) + rol + datos académicos
│   ├── views.py               # Login/logout, perfil, recuperación de contraseña
│   ├── urls.py                # Montado en /cuenta/
│   └── management/commands/
│       └── datos_demo.py      # python manage.py datos_demo (semilla completa)
│
├── materias/                  # 📚 Catálogo y flujo de aprobación (RF-11…15)
│   ├── models.py              # Materia, VersionMateria, SolicitudMateria
│   ├── views.py / forms.py    # Catálogo público, proponer, editar, panel
│   └── urls.py                # Montado en /materias/
│
├── cupos/                     # 🎟️ Ofertas, solicitudes y esperas (RF-05…10)
│   ├── models.py              # OfertaCupo, SolicitudCupo, Inscripcion
│   ├── views.py               # Ofertas, solicitar, inscripciones, lista de espera
│   └── urls.py                # Montado en /cupos/
│
├── mensajes/                  # ✉️ Mensajería trazable (RF-16…20)
│   ├── models.py              # Hilo, Mensaje (leído, intervención secretaría)
│   ├── views.py / forms.py    # Bandeja, nuevo hilo, responder, intervenir
│   └── urls.py                # Montado en /mensajes/
│
├── evaluaciones/              # 📋 Faltas y evaluación docente (RF-21…34)
│   ├── models.py              # Sesion, Falta, ResumenInasistencia,
│   │                          # PeriodoEvaluacion, InvitacionEvaluacion,
│   │                          # RespuestaEvaluacion (anónima)
│   ├── forms.py               # Formulario dinámico de evaluación, asistencia
│   └── urls.py                # Montado en /evaluaciones/
│
├── quejas/                    # 📮 PQRS con escalamiento (RF-35…42)
│   ├── models.py              # CategoriaQueja, Queja, Seguimiento
│   ├── views.py / forms.py    # Radicar, panel, gestionar, vencidos, cierre
│   └── urls.py                # Montado en /quejas/
│
├── reportes/                  # 📊 Reportes y exportación (RF-43…50)
│   ├── models.py              # PlantillaReporte, ReporteGenerado, ProgramacionReporte
│   ├── servicios.py           # Generadores de datos + exportar CSV/XLSX/PDF
│   └── urls.py                # Montado en /reportes/
│
├── analitica/                 # 🧠 Score y predicción de demanda (RF-51…56)
│   ├── models.py              # NecesidadDetectada, PrediccionDemanda, constantes
│   ├── servicios.py           # Detectores automáticos + promedio móvil/regresión
│   └── urls.py                # Montado en /analitica/
│
├── templates/                 # 🎨 Capa de presentación (T del MVT)
│   ├── base.html              # Layout Bootstrap 5: navbar + sidebar por rol
│   ├── dashboard*.html        # Tableros: estudiante / docente / admin / neutro
│   ├── comun/                 # _menu_lateral.html, notificaciones.html
│   ├── usuario/               # login, perfil, 6 plantillas de contraseñas
│   ├── materias/ cupos/ mensajes/          (3-4 plantillas por app)
│   ├── evaluaciones/ quejas/               (5-7 plantillas por app)
│   └── reportes/ analitica/                (3-4 plantillas por app)
│
├── static/
│   └── css/sgdic.css          # Tema propio sobre Bootstrap (tarjetas KPI,
│                              # semáforo, burbujas de chat, sidebar)
├── media/                     # Archivos subidos (evidencias, justificaciones)
│
├── docs/                      # 📄 Documentación fuente del proyecto (PDF/LaTeX)
│   ├── README.md
│   └── secciones/*.tex        # 01_introduccion, 04_requerimientos, 06_algoritmo
├── arquitecura/               # 📄 Documento de arquitectura (build/main_arq.txt)
│
└── .venv/                     # Entorno virtual (no versionar)
```

**Total:** 8 apps de negocio + 1 app transversal (`comun`), 51 plantillas, 17 migraciones.

---

## 4. Módulos, rutas y modelos

| App | Montaje URL | Modelos principales | RF cubiertos |
|-----|-------------|--------------------|--------------|
| `usuario` | `/cuenta/` | `Usuario` | RF-01, RF-02, RF-03 |
| `materias` | `/materias/` | `Materia`, `VersionMateria`, `SolicitudMateria` | RF-11…RF-15 |
| `cupos` | `/cupos/` | `OfertaCupo`, `SolicitudCupo`, `Inscripcion` | RF-05…RF-10 |
| `mensajes` | `/mensajes/` | `Hilo`, `Mensaje` | RF-16…RF-20 |
| `evaluaciones` | `/evaluaciones/` | `Sesion`, `Falta`, `ResumenInasistencia`, `PeriodoEvaluacion`, `InvitacionEvaluacion`, `RespuestaEvaluacion` | RF-21…RF-34 |
| `quejas` | `/quejas/` | `CategoriaQueja`, `Queja`, `Seguimiento` | RF-35…RF-42 |
| `reportes` | `/reportes/` | `PlantillaReporte`, `ReporteGenerado`, `ProgramacionReporte` | RF-43…RF-50 |
| `analitica` | `/analitica/` | `NecesidadDetectada`, `PrediccionDemanda` | RF-51…RF-56 |
| `comun` | — (transversal) | `AuditoriaLog`, `Notificacion` | RF-04, RF-08, RNF-09 |

### 4.2 Mapa de rutas principales

| URL | Vista | Acceso | Función |
|-----|-------|--------|---------|
| `/` | `dashboard` | Autenticado | Tablero con KPIs según el rol |
| `/cuenta/login/`, `/cuenta/logout/` | auth de Django | Público | RF-01 |
| `/cuenta/perfil/` | `perfil` | Autenticado | RF-02 |
| `/cuenta/password/…` | reset/change de Django | mixto | RF-03 |
| `/materias/` | `CatalogoView` | Público | RF-15 |
| `/materias/proponer/` | `proponer_materia` | Docente | RF-11 |
| `/materias/<id>/editar/` | `editar_materia` | Docente | RF-12 |
| `/materias/panel/` | `PanelMateriasView` | Departamento/ADMIN | RF-13 |
| `/cupos/` | `OfertasView` | Autenticado | RF-05 |
| `/cupos/oferta/<id>/solicitar/` | `solicitar_cupo` | Estudiante | RF-05/06 (RN-01…04) |
| `/cupos/mis-solicitudes/` | `MisSolicitudesView` | Estudiante | RF-08 |
| `/cupos/inscripciones/` | `MisInscripcionesView` | Estudiante | RF-09 |
| `/cupos/lista-espera/` | `ListaEsperaView` | Staff | RF-10 |
| `/cupos/procesar-pendientes/` | `procesar_pendientes` | Staff | RF-07 |
| `/mensajes/` | `BandejaView` | Autenticado | RF-16 |
| `/mensajes/nuevo/` | `nuevo_hilo` | Estudiante | RF-16 |
| `/mensajes/<id>/` | `ver_hilo` | Participantes | RF-17/18 |
| `/mensajes/<id>/intervenir/` | `intervenir_hilo` | Secretaría | RF-20 |
| `/evaluaciones/sesiones/` | `registrar_asistencia` | Docente/Staff | RF-21/22 |
| `/evaluaciones/faltas/` | `mis_faltas` | Estudiante | RF-21 |
| `/evaluaciones/faltas/<id>/justificar/` | `justificar_falta` | Estudiante | RF-23 |
| `/evaluaciones/faltas/revisar/` | `revisar_justificaciones` | Docente/Staff | RF-24 |
| `/evaluaciones/inasistencia/` | `panel_inasistencia` | Docente/Staff | RF-25/26 |
| `/evaluaciones/evaluacion/` | `mis_invitaciones` | Estudiante | RF-28/29 |
| `/evaluaciones/evaluacion/<id>/responder/` | `responder_evaluacion` | Estudiante | RF-30 (RN-05) |
| `/evaluaciones/evaluacion/resultados/` | `resultados_docente` | Docente/Staff | RF-32/33 |
| `/evaluaciones/evaluacion/periodos/` | `gestionar_periodos` | Departamento | RF-27/34 |
| `/quejas/` | `mis_quejas` | Autenticado | RF-41 |
| `/quejas/nueva/` | `radicar` | Autenticado | RF-35/36 (RN-09) |
| `/quejas/gestion/` | `panel_gestion` | Staff/Docente | RF-37 |
| `/quejas/escalamientos/` | `casos_vencidos` | Secretaría/Dep. | RF-38 (RN-10) |
| `/quejas/<id>/gestionar/` | `gestionar` | Staff/Docente | RF-39/42 |
| `/quejas/<id>/confirmar/` | `confirmar` | Radicador | RF-42 (RN-12) |
| `/reportes/` | `panel` | Staff/Docente | RF-44 |
| `/reportes/<id>/generar/` | `generar` | Staff/Docente | RF-45 |
| `/reportes/<id>/descargar/?formato=` | `descargar` | Staff/Docente | RF-46 |
| `/reportes/programaciones/` | `programaciones` | Staff | RF-48 |
| `/analitica/` | `tablero` | Staff | RF-53 |
| `/analitica/detectar/` | `detectar` | Staff | RF-51/52 |
| `/analitica/simulador/` | `simulador` | Staff | RF-56 |
| `/analitica/predicciones/` | `predicciones` | Staff | RF-54/55 |
| `/notificaciones/` | `notificaciones` | Autenticado | RF-08 |
| `/admin/` | Django admin | Superusuario | Soporte |

Los detalles completos de cada patrón están en `sgdic/urls.py` y en los
`<app>/urls.py` de cada módulo (todos con `app_name` y `name` para `reverse()`).

---

## 5. Control de acceso (RBAC)

Cinco roles definidos en `usuario.Usuario.rol` y en `comun/models.py`:

| Rol | Valor | Alcance principal |
|-----|-------|-------------------|
| Estudiante | `ESTUDIANTE` | Ofertas de cupos, inscripciones, faltas y justificaciones, mensajería, evaluación docente, radicar/confirmar quejas |
| Docente | `DOCENTE` | Asistencia y justificaciones, panel de inasistencia de sus materias, mensajería, proponer materias, resultados de evaluación, gestión de quejas asignadas, reportes |
| Secretaría | `SECRETARIA` | Listas de espera, procesamiento de cupos, intervención de hilos, gestión/escalamiento de quejas, panel de inasistencia, reportes, recordatorios |
| Departamento | `DEPARTAMENTO` | Todo lo de Secretaría + aprobación de materias, periodos de evaluación, ejecutar detección analítica y generar predicciones |
| Administrador | `ADMIN` | Acceso total (implícito en todos los decoradores) + Django admin |

Mecanismos (`comun/mixins.py`):

```python
rol_usuario(user)            # devuelve el rol o None
requiere_rol("DOCENTE", ...) # decorador para funciones; ADMIN siempre pasa
MixinRol                     # para CBV; usa roles_permitidos = (...)
MixinStaff(MixinRol)         # acceso SECRETARIA/DEPARTAMENTO/ADMIN
```

El menú lateral (`templates/comun/_menu_lateral.html`) y los dashboards
(`templates/dashboard_*.html`) muestran opciones según el rol; el backend
vuelve a validar cada acceso (defensa en profundidad).

---

## 6. Reglas de negocio implementadas (RN-01…RN-12)

| Regla | Descripción | Ubicación |
|-------|-------------|-----------|
| **RN-01** | Prerrequisitos aprobados para solicitar cupo | `SolicitudCupo.cumple_prerrequisitos` → `procesar()` |
| **RN-02** | Respeto del cupo máximo; sin cupos → lista de espera | `SolicitudCupo.procesar()` + `OfertaCupo.cupos_disponibles` |
| **RN-03** | Rechazo por conflicto de horario con inscripción activa | `OfertaCupo.solapa_con()` → `SolicitudCupo.conflicto_horario()` |
| **RN-04** | Prioridad = promedio + avance (semestre/10) + antigüedad | `SolicitudCupo._prioridad_total()` |
| **RN-05** | Anonimato: resultados solo con ≥ 5 respuestas por docente-materia | `RespuestaEvaluacion.puede_publicarse()` + `resultados_docente` |
| **RN-06** | Evaluación habilitada solo dentro de la ventana del periodo | `PeriodoEvaluacion.habilitado` |
| **RN-07** | Notificación de falta al estudiante el mismo día | `Falta.notificar()` |
| **RN-08** | Umbral de inasistencia (20%) con semáforo y alertas | `ResumenInasistencia.calcular()` / `alertar_si_corresponde()` |
| **RN-09** | Confidencialidad del denunciante anónimo | `Queja.anonima` + `identidad_visible` + vistas que lo ocultan |
| **RN-10** | Escalamiento automático sin gestión en 3 días | `Queja.requiere_escalamiento()` / `escalar()` |
| **RN-11** | Soluciones rápidas predefinidas por categoría | `CategoriaQueja.solucion_rapida` → `Queja.aplicar_solucion_rapida()` |
| **RN-12** | Cierre solo con confirmación del usuario (y reapertura) | `Queja.confirmar_cierre()` / `reabrir()` |

---

## 7. Analítica: modelo de priorización (Cap. 6)

El motor de `analitica/servicios.py` ejecuta cuatro detectores sobre los datos
operativos y prioriza las necesidades con la fórmula del documento:

```
score = (I × U) / (E + ε)        ε = 0.5

I  impacto    : CRITICO=4.0 · ALTO=3.0 · MEDIO=2.0 · BAJO=1.0
U  urgencia   : DOCENTE=1.5 · ADMINISTRATIVA=1.3 · INFRAESTRUCTURA=1.2 · TECNOLOGICA=1.1
E  esfuerzo   : horas/hombre estimadas
```

Clasificación: `score ≥ 1.0 → CRÍTICA · ≥ 0.5 → ALTA · ≥ 0.25 → MEDIA · < 0.25 → BAJA`.

**Detectores automáticos (RF-51/RF-52):**

| Detector | Fuente de datos | Umbral |
|----------|-----------------|--------|
| `detectar_necesidades_de_quejas` | categorías con casos recurrentes y baja satisfacción | ≥ 3 casos |
| `detectar_necesidades_de_cupos` | materias con solicitudes en lista de espera | ≥ 5 en espera |
| `detectar_necesidades_de_inasistencia` | resúmenes en riesgo crítico | RN-08 |
| `detectar_necesidades_de_evaluacion` | promedio docente bajo con respuestas suficientes | RN-05 |

**Predicción de demanda (RF-54/RF-55):** serie histórica de inscritos por materia →
regresión lineal simple si R² ≥ 0.5 (método `REG`), si no promedio móvil de los
últimos 3 periodos (método `MM`); cupo sugerido = demanda estimada × 1.1 (+10% de
margen). `actualizar_demanda_real()` contrasta el estimado con lo ocurrido y calcula
el error absoluto.

---

## 8. Flujos de negocio end-to-end

### 8.1 Solicitud de cupo (RF-05…RF-10, RN-01…RN-04)

```
Estudiante            cupos/views.py            cupos/models.py
    │  POST /cupos/oferta/<id>/solicitar/
    ├──────────────────▶ solicitar_cupo()
    │                    get_or_create(SolicitudCupo)
    │                    └────────────▶ solicitud.procesar()  [atomic]
    │                                      1. cumple_prerrequisitos?  ──✗ RECHAZADA (RN-01)
    │                                      2. conflicto_horario()?    ──✗ RECHAZADA (RN-03)
    │                                      3. cupos_disponibles > 0?  ──✓ APROBADA (RN-02)
    │                                         + Inscripcion ACTIVA + inscritos+1
    │                                      4. si no                  ── EN_ESPERA (RN-02)
    │                                      5. prioridad = _prioridad_total() (RN-04)
    │                    Notificacion.enviar(estudiante, resultado)
    ◀──────────────────── redirect con mensaje flash
Secretaría: /cupos/procesar-pendientes/ procesa las PENDIENTE por prioridad (RN-04)
            /cupos/lista-espera/       supervisa y libera cupos
```

### 8.2 Inasistencia y alertas (RF-21…RF-26, RN-07/RN-08)

```
Docente crea Sesion (/evaluaciones/sesiones/) ──▶ marca ausentes (RegistroFaltasForm)
   └─ por cada ausente: Falta.get_or_create → falta.notificar()  (RN-07: mismo día)
                        → _recalcular_resumen()
                            ├─ ResumenInasistencia.calcular()
                            │    % = faltas efectivas × 100 / total sesiones
                            │    ≥ 20% → CRIT · ≥ 15% → WARN · si no → OK (RN-08)
                            └─ alertar_si_corresponde()
                                 → CRIT: notifica a estudiante + docentes
                                   de la materia + Secretaría/Departamento
Estudiante: /evaluaciones/faltas/ → justificar con evidencia (RF-23)
Docente:    /evaluaciones/faltas/revisar/ → aprobar/rechazar (RF-24)
            (las justificadas se excluyen del cálculo del porcentaje)
```

### 8.3 Evaluación docente anónima (RF-27…RF-34, RN-05/RN-06)

```
Departamento configura PeriodoEvaluacion (/evaluaciones/evaluacion/periodos/)
   └─ al guardar activo: se desactivan otros periodos y se generan
      InvitacionEvaluacion por (estudiante, docente, materia inscrita)  (RF-29)
Estudiante responde /evaluaciones/evaluacion/<id>/responder/
   └─ formulario dinámico con las preguntas del periodo (escala 1-5)
   └─ NO se guarda el autor: se crea RespuestaEvaluacion consolidada
      (puntuación promedio + detalle JSON + comentario opcional)
Secretaría envía recordatorios a los pendientes (RF-29)
Resultados /evaluaciones/evaluacion/resultados/ (RF-32/33):
   └─ publicables solo si respuestas ≥ SGDIC_MIN_RESPUESTAS_ANONIMO (RN-05)
```

### 8.4 Quejas con escalamiento (RF-35…RF-42, RN-09…RN-12)

```
Usuario radica /quejas/nueva/ (categoría, asunto, descripción, evidencia,
   opción anónima RN-09) → consecutivo Q-AAAA-NNNNN + sugerencia inmediata
   si la categoría tiene solución rápida (RN-11)
Secretaría/Docente gestiona /quejas/<id>/gestionar/:
   ASIGNAR → EN_PROCESO (RF-37) · AVANCE (RF-40) · RESOLVER (RF-39)
   SOLUCION_RAPIDA (RN-11) · ESCALAR manual
Escalamiento automático (RN-10): /quejas/escalamientos/ detecta los que llevan
   ≥ SGDIC_DIAS_ESCALAMIENTO (3) días sin gestión y los escala masivamente;
   Queja.escalar() notifica a Secretaría + Departamento.
Radicador: /quejas/<id>/confirmar/ → califica 1-5 y cierra (RN-12)
   o reabre el caso si persiste el problema (RN-12).
```

### 8.5 Reportes y analítica (RF-43…RF-56)

```
Staff genera /reportes/<id>/generar/ → ReporteGenerado (PENDIENTE→LISTO/ERROR)
   con la matriz de datos de reportes/servicios.py (7 tipos de reporte)
Descarga /reportes/<id>/descargar/?formato=CSV|XLSX|PDF (RF-46)
   XLSX y PDF requieren openpyxl/reportlab; si faltan, cae a CSV.
Programaciones (RF-48): frecuencia DIARIA/SEMANAL/MENSUAL → próxima ejecución;
   "Ejecutar vencidas" genera el reporte y notifica a los destinatarios.
Analítica: /analitica/detectar/ ejecuta los 4 detectores → NecesidadDetectada
   (score automático) → tablero priorizado /analitica/ (RF-53)
   → /analitica/predicciones/ genera cupos sugeridos por materia (RF-54/55)
   → /analitica/simulador/ recalcula (I×U)/(E+ε) en vivo (RF-56).
```

---

## 9. Servicios transversales

### 9.1 Notificaciones (`comun/models.py`)

```python
Notificacion.enviar(destinatario, titulo, cuerpo, url="", nivel=INFO|WARN|CRIT, correo=True)
```

- Crea el registro in-app (bandeja `/notificaciones/`) y envía correo con
  `fail_silently=True` usando `EMAIL_BACKEND` (consola en desarrollo).
- La usan: cupos (resultado de solicitud), mensajes (nuevo hilo, respuesta,
  intervención), evaluaciones (falta, alerta de inasistencia, recordatorios),
  quejas (asignación, solución, escalamiento) y reportes (envíos programados).

### 9.2 Auditoría (`AuditoriaLog`, RNF-09)

`AuditoriaLog.registrar(request, accion, objeto, detalle)` registra usuario,
acción, tipo/ID de objeto y fecha. Eventos registrados: `RADICAR_QUEJA`,
`QUEJA_<ACCIÓN>`, `GENERAR_REPORTE`, `DESCARGAR_REPORTE`. Inmutable (solo
lectura en el admin).

### 9.3 KPIs (`comun/kpi.py`)

`tablero_kpis(usuario)` devuelve el consolidado según el rol:

| Rol | Indicadores |
|-----|-------------|
| Estudiante | inscripciones activas, evaluaciones pendientes, notificaciones |
| Docente | hilos activos, puntaje promedio de evaluación, notificaciones |
| Secretaría/Dep./Admin | ocupación y cupos, quejas (abiertas / en proceso / escaladas / horas de cierre / satisfacción), participación y puntaje de evaluación, inasistencia en riesgo, solicitudes de materias pendientes |

### 9.4 Middleware de configuración (`comun/middleware.py`)

Inyecta `request.sgdic_config` con los parámetros de negocio
(`umbral_inasistencia`, `horas_respuesta`, `dias_escalamiento`,
`min_respuestas_anonimo`) tomados de `settings`, de modo que las vistas usan
valores configurables y no constantes.

---

## 10. Puesta en marcha

### 10.1 Requisitos y arranque

- Python 3.10+ (desarrollado y probado con Python 3.12)
- Django 4.2 LTS instalado en el entorno virtual `.venv/`
- Opcional para exportación avanzada: `pip install openpyxl reportlab`

```powershell
# 1) Activar el entorno virtual (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 2) Aplicar migraciones (crea/actualiza el esquema)
python manage.py migrate

# 3) Cargar datos de demostración (idempotente; recrea lo que falte)
python manage.py datos_demo

# 4) (Opcional) crear otro superusuario para /admin/
python manage.py createsuperuser

# 5) Levantar el servidor de desarrollo
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/> e iniciar sesión. El catálogo de materias
(`/materias/`) y el login son públicos; el resto exige autenticación.

> La base de desarrollo ya está creada (`db.sqlite3`) con datos demo cargados;
> los pasos 2 y 3 son para reconstruir desde cero.

### 10.2 Cuentas de la demo (`datos_demo`)

Contraseña para **todos** los usuarios demo: `Sgdic2026*`

| Usuario | Rol | Escenario cargado |
|---------|-----|-------------------|
| `admin_sgdic` | ADMIN (superusuario) | Acceso total + `/admin/` |
| `secretaria` | SECRETARIA | Listas de espera, gestión de quejas, un caso asignado |
| `jefe_departamento` | DEPARTAMENTO | Aprobación de materias, periodos de evaluación, analítica |
| `jlopez` | DOCENTE | 3 materias dictadas, hilo con estudiante, queja resuelta |
| `mgarcia` | DOCENTE | 2 materias dictadas, hilo sin responder (para RF-20) |
| `esteban` | ESTUDIANTE | 7º semestre, promedio 4.35, inscripciones activas, 3 faltas (1 justificada), hilo, queja resuelta |
| `ana` | ESTUDIANTE | 5º semestre, promedio 4.10, hilo pendiente, queja anónima escalada |
| `carlos` | ESTUDIANTE | 3º semestre, promedio 3.60, queja en proceso |

Datos que trae la semilla: 5 materias con prerrequisitos y docentes, 15 ofertas
(3 periodos), inscripciones históricas 2025 (base de la predicción), solicitudes
de cupo procesadas y una oferta saturada con lista de espera, 6 sesiones por
oferta 2026-1 con faltas y resúmenes de inasistencia (uno en riesgo crítico),
2 hilos de mensajería, 4 categorías de queja con soluciones rápidas y 3 casos
(resuelto / escalado / en proceso), periodo de evaluación activo con 16
respuestas anónimas, 7 plantillas de reporte, predicciones de demanda y
necesidades detectadas.

---

## 11. Configuración (`sgdic/settings.py`)

Todas las decisiones sensibles se toman con variables de entorno (prefijo
`SGDIC_`); en su ausencia se usan valores de desarrollo:

| Variable | Predeterminada | Uso |
|----------|----------------|-----|
| `SGDIC_SECRET_KEY` | clave de desarrollo | Clave criptográfica de Django |
| `SGDIC_DEBUG` | `1` | `0` para producción |
| `SGDIC_DB_ENGINE` | `django.db.backends.sqlite3` | `django.db.backends.postgresql` para producción |
| `SGDIC_DB_NAME` / `SGDIC_DB_USER` / `SGDIC_DB_PASSWORD` / `SGDIC_DB_HOST` / `SGDIC_DB_PORT` | `sgdic` / `sgdic` / — / `localhost` / `5432` | Conexión a PostgreSQL |

Parámetros de negocio (reglas del documento técnico):

```python
SGDIC_UMBRAL_INASISTENCIA = 20     # % que dispara riesgo crítico (RN-08)
SGDIC_HORAS_RESPUESTA     = 48     # horas de mensajería antes de intervenir (RF-20)
SGDIC_DIAS_ESCALAMIENTO   = 3      # días sin gestionar una queja (RN-10)
SGDIC_MIN_RESPUESTAS_ANONIMO = 5   # respuestas mínimas para publicar (RN-05)
```

Otros ajustes: `LANGUAGE_CODE="es"`, `TIME_ZONE="America/Bogota"`,
`AUTH_USER_MODEL="usuario.Usuario"`, `LOGIN_URL="usuario:login"`,
`LOGIN_REDIRECT_URL="dashboard"`, `EMAIL_BACKEND` de consola, `STATIC_URL`/
`STATIC_ROOT`/`MEDIA_*` para archivos, y el middleware propio
`comun.middleware.ConfiguracionSGDIC` al final de `MIDDLEWARE`.

---

## 12. Pruebas

```powershell
# Suite completa (20 pruebas)
python manage.py test sgdic

# Suite con detalle
python manage.py test sgdic -v 2

# Verificar que no falten migraciones
python manage.py makemigrations --check --dry-run

# Chequeo general del proyecto
python manage.py check
```

Cobertura de `sgdic/tests.py`:

| Clase | Qué valida |
|-------|-----------|
| `PruebasReglasCupo` | RN-01 (rechazo por prerrequisitos / aprobación con ellos), RN-02 (lista de espera al agotar cupo), RN-03 (conflicto de horario), incremento de `inscritos` y creación de `Inscripcion` |
| `PruebasAnalitica` | Fórmula exacta del score `(4×1.5)/(8+0.5)=0.7059`, clasificación CRITICA/ALTA/MEDIA/BAJA, predicción con histórico y cupo sugerido |
| `PruebasQuejas` | RN-10 (vencimiento y `escalar()`), RN-11 (solución rápida resuelve y registra en la bitácora), RN-12 (cierre con calificación), unicidad del consecutivo `Q-…` |
| `PruebasVistas` | Login + dashboard por rol, 302 sin sesión, catálogo público, solicitud de cupo por POST, RBAC (403 estudiante / 200 secretaría), bandeja de mensajes, notificaciones (marcado de lectura), radicación de queja con trazabilidad, `tablero_kpis` por rol |

Además de la suite automatizada, se ejecutó una **prueba de humo manual**
recorriendo 46 rutas con los 5 roles contra la base demo: todas HTTP 200.

---

## 13. Despliegue en producción

1. **Variables de entorno** (no commitear secretos):

```powershell
$env:SGDIC_DEBUG = "0"
$env:SGDIC_SECRET_KEY = "<clave larga y aleatoria>"
$env:SGDIC_DB_ENGINE  = "django.db.backends.postgresql"
$env:SGDIC_DB_NAME = "sgdic";  $env:SGDIC_DB_USER = "sgdic"
$env:SGDIC_DB_PASSWORD = "<password>";  $env:SGDIC_DB_HOST = "localhost"
```

2. **Ajustes recomendados en `settings.py`**: restringir `ALLOWED_HOSTS`
   (hoy `["*"]` solo para desarrollo) y cambiar `EMAIL_BACKEND` a SMTP real.

3. **Migraciones y estáticos:**

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
```

4. **Servidor WSGI** (punto de entrada: `sgdic.wsgi.application`):

```bash
gunicorn sgdic.wsgi:application --bind 0.0.0.0:8000 --workers 3   # Linux
waitress-serve --port=8000 sgdic.wsgi:application                  # Windows
```

5. **Proxy inverso** (Nginx/IIS) sirviendo `/static/` y `/media/` desde
   `STATIC_ROOT` y `MEDIA_ROOT`, con `DEBUG=False`.

6. **Tareas periódicas** (cron / Programador de tareas de Windows) invocando la
   lógica equivalente a: ejecutar programaciones de reportes (RF-48), escalar
   quejas vencidas (RN-10) y enviar recordatorios de evaluación (RF-29).

### 13.1 Despliegue en Vercel (implementado)

El proyecto está configurado para desplegarse en Vercel con el formato
`services` de `vercel.json` (servicio `sgdic-web`, runtime Python, entrypoint
`sgdic/wsgi.py`, build con `bash build.sh`). Pasos realizados:

```bash
vercel link --yes --project proyectoasi-sgdic
vercel env add SGDIC_SECRET_KEY production      # clave larga y aleatoria
vercel env add SGDIC_DEBUG production           # "0"
vercel env add SGDIC_ALLOWED_HOSTS production   # ".vercel.app"
vercel env add SGDIC_CSRF_TRUSTED_ORIGINS production  # "https://*.vercel.app"
vercel --prod
```

Notas de la plataforma:

- **Estáticos**: servidos por WhiteNoise (`CompressedManifestStaticFilesStorage`),
  no requieren CDN adicional.
- **Base de datos**: sin `DATABASE_URL`, la función copia `db.sqlite3` a `/tmp`
  al arranque (única ruta escribible). Los datos son **efímeros por instancia**;
  para persistencia real definir `DATABASE_URL` de un PostgreSQL externo
  (Neon, Supabase, etc.), el `settings.py` ya lo soporta.
- **`media/`**: no persiste entre invocaciones (filesystem de solo lectura).
- Cada push a GitHub conectado con `vercel git connect` genera un despliegue.

---

---

## 14. Trazabilidad con la documentación

| Fuente | Contenido | Reflejo en el código |
|--------|-----------|----------------------|
| `docs/secciones/04_requerimientos.tex` | RF-01…RF-56, RN-01…RN-12 | Comentarios `# RF-xx` / `# RN-xx` en cada módulo; tablas de las secciones 4 y 6 |
| `arquitecura/build/main_arq.txt` | Arquitectura MVT de 3 capas, 8 apps, PostgreSQL | Secciones 2 y 3; `INSTALLED_APPS`; configuración de BD |
| `docs/secciones/06_algoritmo.tex` | Score (I×U)/(E+ε), factores y umbrales | `analitica/models.py` (constantes) y `analitica/servicios.py` (motor) |
| `docs/uml/class_diagram.puml` | Diagrama de clases del dominio | Modelos de cada app con nombres y relaciones equivalentes |

---

## 15. Estado del proyecto

- [x] Autenticación, perfiles y recuperación de contraseña (RF-01…03)
- [x] RBAC de 4 roles + ADMIN con menús y decoradores (RF-02)
- [x] Auditoría y notificaciones transversales (RF-04, RF-08)
- [x] Cupos con lista de espera y priorización (RF-05…10, RN-01…04)
- [x] Preinscripción de asignaturas con probabilidad, horarios y prioridad (RN-13, RN-14)
- [x] Catálogo con flujo de aprobación y versiones (RF-11…15)
- [x] Mensajería trazable con intervención (RF-16…20)
- [x] Faltas, justificaciones y alertas de inasistencia (RF-21…26, RN-07/08)
- [x] Evaluación docente anónima (RF-27…34, RN-05/06)
- [x] Quejas con escalamiento y cierre confirmado (RF-35…42, RN-09…12)
- [x] Reportes CSV/Excel/PDF programables (RF-43…50)
- [x] Analítica de priorización y predicción de demanda (RF-51…56)
- [x] 51 plantillas Bootstrap 5 + dashboards por rol
- [x] Datos demo y comando de semilla idempotente
- [x] 20 pruebas automatizadas en verde + smoke test de 46 rutas × 5 roles

**Pendiente / mejoras futuras:** convertir las tareas periódicas (programaciones
de reportes, escalamiento de quejas, recordatorios) en comandos de gestión con
cron/CEST; implementar el bloqueo de servicios mientras el estudiante no evalúe
(RF-31, el flag `PeriodoEvaluacion.bloquear_servicios` ya existe en el modelo);
añadir pruebas de `evaluaciones` y `reportes` a la suite automatizada.








