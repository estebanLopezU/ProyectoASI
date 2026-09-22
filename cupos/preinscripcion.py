# =====================================================================
# Motor de preinscripción de asignaturas (RN-13, RN-14)
#
# Calcula, para cada materia que un estudiante desea cursar:
#   * demanda agregada   → cuántos estudiantes la preinscribieron
#   * preferencia media  → qué tan arriba la pusieron en su lista
#   * predicción         → demanda histórica estimada (RF-54, Cap. 6)
#   * docentes activos   → oferta docente disponible para abrir grupos
#   * compatibilidad     → franja libre de choques con lo ya inscrito
#
# El resultado es una probabilidad 0-1 de obtener el cupo si se aprueba
# la apertura del grupo.
# =====================================================================
from datetime import time

from django.db.models import Avg, Count

from .models import Inscripcion, OfertaCupo, PreferenciaPreinscripcion, Preinscripcion

# --- Factores del modelo (paralelos a los del Cap. 6 analítico) -------
PESO_DEMANDA = 0.40      # cuánta gente la quiere
PESO_PREFERENCIA = 0.25  # qué tan alta es la preferencia promedio
PESO_HISTORICO = 0.20    # predicción de demanda histórica
PESO_DOCENTES = 0.15     # disponibilidad docente (oferta real de grupos)
EPSILON = 0.5

# ---------------------------------------------------------------------
# Franjas horarias: etiqueta → (inicio, fin)
# ---------------------------------------------------------------------
FRANJAS = {
    PreferenciaPreinscripcion.Franja.MANANA: (time(7, 0), time(12, 0)),
    PreferenciaPreinscripcion.Franja.TARDE: (time(12, 0), time(18, 0)),
    PreferenciaPreinscripcion.Franja.NOCHE: (time(18, 0), time(22, 0)),
}


def periodo_objetivo_actual():
    """Periodo siguiente al último ofertado (o el del año en curso)."""
    ultimo = OfertaCupo.objects.order_by("-periodo").values_list("periodo", flat=True).first()
    if not ultimo:
        from django.utils import timezone
        return f"{timezone.localdate().year}-1"
    from analitica.servicios import _periodo_siguiente
    return _periodo_siguiente(ultimo)


def _horas_ocupadas(estudiante):
    """Franjas ya ocupadas por las inscripciones activas del estudiante."""
    ocupadas = []
    inscripciones = (Inscripcion.objects
                     .filter(estudiante=estudiante, estado=Inscripcion.Estado.ACTIVA)
                     .select_related("oferta"))
    for inscripcion in inscripciones:
        ocupadas.append((inscripcion.oferta.dia,
                         inscripcion.oferta.hora_inicio,
                         inscripcion.oferta.hora_fin))
    return ocupadas


def _slot_libre(dia, inicio, fin, ocupadas):
    """Determina si un rango horario choca con las franjas ocupadas."""
    for dia_ocupado, ini, f in ocupadas:
        if dia_ocupado == dia and inicio < f and ini < fin:
            return False
    return True


def construir_horario(estudiante, reservadas=()):
    """RN-14: propone una rejilla horaria semanal sin choques.

    `reservadas` permite marcar franjas ya asignadas a otras materias
    preinscritas para que la sugerencia no las repita.

    Devuelve una lista de dicts con día, franja, rango y si el espacio
    está libre o ya ocupado por una inscripción activa.
    """
    ocupadas = _horas_ocupadas(estudiante)
    reservadas = list(reservadas)
    rejilla = []
    for valor_dia, nombre_dia in PreferenciaPreinscripcion.DIAS:
        for franja, (inicio, fin) in FRANJAS.items():
            clave = f"{valor_dia}:{franja}"
            rejilla.append({
                "dia": valor_dia,
                "nombre_dia": nombre_dia,
                "franja": franja,
                "clave": clave,
                "etiqueta": PreferenciaPreinscripcion.Franja(franja).label,
                "inicio": inicio,
                "fin": fin,
                "libre": _slot_libre(valor_dia, inicio, fin, ocupadas),
                "reservada": clave in reservadas,
            })
    return rejilla


def franjas_estudiante(estudiante, periodo):
    """Franjas preferidas declaradas por el estudiante para el periodo."""
    return list(PreferenciaPreinscripcion.objects.filter(
        estudiante=estudiante, periodo_objetivo=periodo))


def docentes_activos(materia):
    """Docentes activos asignados a la materia."""
    return materia.docentes.filter(is_active=True).count()


def demanda_historica(materia, periodo):
    """Demanda estimada con el motor analítico (RF-54); 0 si no hay histórico."""
    from analitica.servicios import predecir_materia

    prediccion = predecir_materia(materia, periodo)
    return prediccion.demanda_estimada if prediccion else 0


def grupos_materia(materia, periodo):
    """Grupos (OfertaCupo) activos de una materia en un periodo.

    Cada grupo trae su docente, horario y cupo disponible.  Ordenados por
    día → hora → grupo para presentación consistente en la interfaz.
    """
    return list(OfertaCupo.objects.filter(
        materia=materia, periodo=periodo, activa=True,
    ).select_related("materia").order_by("dia", "hora_inicio", "grupo"))


def calcular_probabilidades(periodo=None, estudiante=None):
    """Calcula la probabilidad de asignación de cada preinscripción.

    Solo recalcula las preinscripciones del periodo (y del estudiante si se
    indica). Devuelve la lista de preinscripciones actualizadas.
    """
    periodo = periodo or periodo_objetivo_actual()
    consulta = Preinscripcion.objects.filter(periodo_objetivo=periodo)
    if estudiante:
        consulta = consulta.filter(estudiante=estudiante)

    # Demanda y preferencia agregadas por materia (todos los estudiantes)
    agregados = {
        fila["materia_id"]: fila
        for fila in (Preinscripcion.objects
                     .filter(periodo_objetivo=periodo)
                     .values("materia_id")
                     .annotate(total=Count("id"), preferencia=Avg("prioridad")))
    }
    if not agregados:
        return []

    max_demanda = max(f["total"] for f in agregados.values()) or 1
    max_preferencia = max((f["preferencia"] or 1) for f in agregados.values()) or 1

    actualizadas = []
    reservadas = set()
    # Orden por prioridad: las materias más preferidas eligen franja primero
    for preinscripcion in consulta.select_related("materia").order_by("prioridad"):
        fila = agregados.get(preinscripcion.materia_id, {"total": 1, "preferencia": 1})
        demanda = fila["total"]
        preferencia_media = fila["preferencia"] or 1

        # Componentes normalizados 0-1
        c_demanda = demanda / max_demanda
        # Menor prioridad numérica = más preferida → mayor puntaje
        c_preferencia = 1 - ((preferencia_media - 1) / max(max_preferencia - 1, 1))

        historico = demanda_historica(preinscripcion.materia, periodo)
        c_historico = min(historico / max(max_demanda * 1.2, 1), 1)

        docentes = docentes_activos(preinscripcion.materia)
        c_docentes = min(docentes / 2, 1)  # 2+ docentes = cobertura completa

        # Cupo esperado: penaliza las materias muy solicitadas (más demanda
        # por el mismo número de grupos ⇒ menor probabilidad individual)
        c_cupo = min(1.0, (max_demanda * 0.6) / (demanda + EPSILON)) if demanda else 1.0

        probabilidad = (
            PESO_DEMANDA * c_demanda * c_cupo
            + PESO_PREFERENCIA * c_preferencia
            + PESO_HISTORICO * c_historico
            + PESO_DOCENTES * c_docentes
        )
        preinscripcion.probabilidad = max(0.0, min(round(probabilidad, 4), 0.99))
        preinscripcion.demanda_estimada = round(historico, 2)
        preinscripcion.docentes_activos = docentes

        # Franja sugerida: primera franja libre y no reservada por otra materia
        horario = construir_horario(preinscripcion.estudiante, reservadas=reservadas)
        libre = next((s for s in horario if s["libre"] and not s["reservada"]), None)
        if libre:
            reservadas.add(libre["clave"])
            preinscripcion.franja_sugerida = (
                f"{libre['nombre_dia']} {libre['inicio']:%H:%M}-{libre['fin']:%H:%M}"
            )
        else:
            preinscripcion.franja_sugerida = ""
        if not docentes:
            preinscripcion.observacion = "Sin docentes activos: no se puede abrir grupo."
        elif preinscripcion.probabilidad < 0.3:
            preinscripcion.observacion = "Alta demanda o cupo limitado: tenga una alternativa."
        else:
            preinscripcion.observacion = ""

        preinscripcion.save(update_fields=[
            "probabilidad", "demanda_estimada", "docentes_activos",
            "franja_sugerida", "observacion",
        ])
        actualizadas.append(preinscripcion)
    return actualizadas


def resumen_preinscripcion(estudiante, periodo=None):
    """RF-49: indicadores de la preinscripción del estudiante."""
    periodo = periodo or periodo_objetivo_actual()
    lista = list(Preinscripcion.objects
                 .filter(estudiante=estudiante, periodo_objetivo=periodo)
                 .select_related("materia"))
    total = len(lista)
    promedio = round(sum(p.probabilidad for p in lista) / total, 3) if total else 0
    return {
        "periodo": periodo,
        "total": total,
        "minimo": Preinscripcion.MINIMO_MATERIAS,
        "faltantes": max(Preinscripcion.MINIMO_MATERIAS - total, 0),
        "cumple_minimo": total >= Preinscripcion.MINIMO_MATERIAS,
        "probabilidad_promedio": promedio,
        "creditos": sum(p.materia.creditos for p in lista),
        "en_riesgo": [p for p in lista if p.probabilidad < 0.3],
    }


def alertas_prerrequisitos(estudiante, periodo=None):
    """RN-01 preventiva: materias preinscritas con prerrequisitos pendientes."""
    periodo = periodo or periodo_objetivo_actual()
    aprobadas = set(
        Inscripcion.objects.filter(estudiante=estudiante,
                                   estado=Inscripcion.Estado.APROBADA)
        .values_list("oferta__materia__codigo", flat=True)
    )
    alertas = []
    for preinscripcion in (Preinscripcion.objects
                           .filter(estudiante=estudiante, periodo_objetivo=periodo)
                           .select_related("materia")):
        requeridos = set(preinscripcion.materia.prerrequisitos
                         .values_list("codigo", flat=True))
        faltantes = requeridos - aprobadas
        if faltantes:
            alertas.append({"preinscripcion": preinscripcion,
                            "faltantes": sorted(faltantes)})
    return alertas
