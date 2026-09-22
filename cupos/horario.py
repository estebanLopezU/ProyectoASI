# =====================================================================
# Franja horaria semanal (calendario de clases)
#
# Construye una rejilla de horas (filas) × días (columnas) con bloques
# de color por materia, para estudiantes (materias que cursan) y
# docentes (materias que dictan). Reutiliza OfertaCupo.dia/hora_inicio/
# hora_fin, que ya son la fuente de verdad del horario (RN-03).
# =====================================================================
from datetime import time, timedelta

from .models import Inscripcion, OfertaCupo, Preinscripcion

# --- Configuración de la rejilla -------------------------------------
HORA_INICIO = 6      # primera hora visible
HORA_FIN = 22        # última hora visible (exclusiva)
PASO_MINUTOS = 60    # granularidad de las filas
DIAS_SEMANA = ((1, "Lunes"), (2, "Martes"), (3, "Miércoles"),
               (4, "Jueves"), (5, "Viernes"), (6, "Sábado"))

PALETA = ("horario-color-0", "horario-color-1", "horario-color-2",
          "horario-color-3", "horario-color-4", "horario-color-5")


def _a_minutos(valor):
    """Convierte time o string 'HH:MM' a minutos desde medianoche."""
    if isinstance(valor, time):
        return valor.hour * 60 + valor.minute
    try:
        horas, minutos = str(valor).split(":")[:2]
        return int(horas) * 60 + int(minutos)
    except (ValueError, AttributeError):
        return 0


def filas_horarias():
    """Lista de etiquetas de hora para el eje vertical."""
    filas = []
    minuto = HORA_INICIO * 60
    while minuto < HORA_FIN * 60:
        filas.append(f"{minuto // 60:02d}:{minuto % 60:02d}")
        minuto += PASO_MINUTOS
    return filas


def _clase_para(indice):
    """Asigna un color estable de la paleta según el índice de materia."""
    return PALETA[indice % len(PALETA)]


def _docentes_texto(materia, docente=None):
    if docente:
        return docente.get_full_name() or docente.username
    nombres = [d.get_full_name() or d.username for d in materia.docentes.all()]
    return ", ".join(nombres) if nombres else "Sin docente asignado"


def _bloque(materia, oferta, indice, rol, extra=""):
    """Construye el dict de un bloque de clase del calendario."""
    return {
        "materia": materia,
        "oferta": oferta,
        "dia": oferta.dia,
        "inicio": oferta.hora_inicio,
        "fin": oferta.hora_fin,
        "inicio_min": _a_minutos(oferta.hora_inicio),
        "fin_min": _a_minutos(oferta.hora_fin),
        "etiqueta_hora": f"{oferta.hora_inicio:%H:%M}",
        "titulo": f"{materia.codigo} · {materia.nombre}",
        "detalle": extra,
        "color": _clase_para(indice),
        "preliminar": False,
        "rol": rol,
    }


def bloques_estudiante(estudiante, periodo=None):
    """Materias que el estudiante cursa (inscripciones activas)."""
    consulta = (Inscripcion.objects
                .filter(estudiante=estudiante, estado=Inscripcion.Estado.ACTIVA)
                .select_related("oferta", "oferta__materia")
                .prefetch_related("oferta__materia__docentes"))
    if periodo:
        consulta = consulta.filter(oferta__periodo=periodo)

    bloques = []
    for indice, inscripcion in enumerate(consulta.order_by("oferta__dia",
                                                           "oferta__hora_inicio")):
        oferta = inscripcion.oferta
        bloques.append(_bloque(
            oferta.materia, oferta, indice, "ESTUDIANTE",
            extra=_docentes_texto(oferta.materia),
        ))
    return bloques


def bloques_docente(docente, periodo=None):
    """Materias que el docente dicta (ofertas de sus materias asignadas)."""
    consulta = (OfertaCupo.objects
                .filter(materia__docentes=docente)
                .select_related("materia")
                .distinct())
    if periodo:
        consulta = consulta.filter(periodo=periodo)

    bloques = []
    for indice, oferta in enumerate(consulta.order_by("dia", "hora_inicio")):
        bloques.append(_bloque(
            oferta.materia, oferta, indice, "DOCENTE",
            extra=f"{oferta.inscritos}/{oferta.cupo_maximo} inscritos · {oferta.periodo}",
        ))
    return bloques


def bloques_preinscripcion(estudiante, periodo):
    """Materias preinscritas ubicadas en su franja sugerida (preliminar)."""
    dia_por_nombre = {nombre: valor for valor, nombre in DIAS_SEMANA}
    bloques = []
    consulta = (Preinscripcion.objects
                .filter(estudiante=estudiante, periodo_objetivo=periodo)
                .select_related("materia")
                .order_by("prioridad"))
    for indice, preinscripcion in enumerate(consulta):
        if not preinscripcion.franja_sugerida:
            continue
        # Formato esperado: "Lunes 12:00-18:00"
        try:
            nombre_dia, rango = preinscripcion.franja_sugerida.split(" ")
            inicio, fin = rango.split("-")
        except ValueError:
            continue
        dia = dia_por_nombre.get(nombre_dia)
        if not dia:
            continue
        bloques.append({
            "materia": preinscripcion.materia,
            "oferta": None,
            "dia": dia,
            "inicio": inicio,
            "fin": fin,
            "inicio_min": _a_minutos(inicio),
            "fin_min": _a_minutos(fin),
            "etiqueta_hora": inicio,
            "titulo": f"{preinscripcion.materia.codigo} · {preinscripcion.materia.nombre}",
            "detalle": (f"Preinscrita P{preinscripcion.prioridad} · "
                        f"{preinscripcion.porcentaje}%"),
            "color": _clase_para(indice),
            "preliminar": True,
            "rol": "ESTUDIANTE",
        })
    return bloques


def _clave_celda(minuto):
    """Índice de fila para un minuto dado, relativo a HORA_INICIO."""
    return (minuto - HORA_INICIO * 60) // PASO_MINUTOS


def _filas_ocupadas_bloque(minuto_inicio, minuto_fin):
    """Número de filas que abarca un bloque (mínimo 1)."""
    inicio = _clave_celda(max(minuto_inicio, HORA_INICIO * 60))
    # Redondeo hacia arriba del fin para cubrir bloques que no calzan exacto
    fin = -(-(minuto_fin - HORA_INICIO * 60) // PASO_MINUTOS)
    return max(fin - inicio, 1)


def construir_rejilla(bloques):
    """Convierte los bloques en una matriz de celdas para la plantilla.

    Devuelve `filas`: lista de dicts {hora, indice, celdas} donde cada
    celda es {"omitida": bool, "bloque": dict|None}. Los bloques que
    abarcan varias horas usan `filas_ocupadas` (rowspan) y las celdas
    cubiertas se marcan como omitidas.
    """
    horas = filas_horarias()
    total_filas = len(horas)
    filas = [{"hora": hora, "indice": indice,
              "celdas": [{"omitida": False, "bloque": None}
                         for _ in DIAS_SEMANA]}
             for indice, hora in enumerate(horas)]

    for bloque in sorted(bloques, key=lambda b: (b["dia"], b["inicio_min"])):
        columna = next((i for i, (valor, _) in enumerate(DIAS_SEMANA)
                        if valor == bloque["dia"]), None)
        if columna is None:
            continue
        inicio = _clave_celda(max(bloque["inicio_min"], HORA_INICIO * 60))
        if inicio >= total_filas:
            continue
        abarca = _filas_ocupadas_bloque(bloque["inicio_min"], bloque["fin_min"])
        abarca = min(abarca, total_filas - inicio)
        bloque["filas_ocupadas"] = abarca
        celda = filas[inicio]["celdas"][columna]
        if celda["bloque"] is not None:
            continue  # ya hay otra clase en esa celda: se conserva la primera
        celda["bloque"] = bloque
        for desplazamiento in range(1, abarca):
            filas[inicio + desplazamiento]["celdas"][columna]["omitida"] = True
    return filas


def rango_semana(hoy=None):
    """Rango lunes-domingo de la semana actual para la cabecera."""
    from django.utils import timezone

    hoy = hoy or timezone.localdate()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)
    return lunes, domingo, hoy


def calcular_colision(bloques):
    """RN-03: detecta clases solapadas en la rejilla (mismo día y hora)."""
    colisiones = []
    for i, primero in enumerate(bloques):
        for segundo in bloques[i + 1:]:
            if (primero["dia"] == segundo["dia"]
                    and primero["inicio_min"] < segundo["fin_min"]
                    and segundo["inicio_min"] < primero["fin_min"]):
                colisiones.append((primero, segundo))
    return colisiones


def resumen_horario(bloques, rol):
    """Indicadores para la cabecera del calendario."""
    materias = {b["materia"].pk for b in bloques}
    confirmados = [b for b in bloques if not b["preliminar"]]
    return {
        "rol": rol,
        "total_bloques": len(bloques),
        "total_materias": len(materias),
        "horas_semanales": round(
            sum(b["fin_min"] - b["inicio_min"] for b in bloques) / 60, 1),
        "bloques_confirmados": len(confirmados),
        "bloques_preliminares": len(bloques) - len(confirmados),
        "dias_con_clase": len({b["dia"] for b in bloques}),
    }


def periodo_vigente(usuario=None, rol="ESTUDIANTE"):
    """Periodo con datos reales de horario para el usuario.

    Prioriza el periodo de las ofertas donde hay inscripciones activas
    (estudiante) o materias asignadas (docente); si no hay, cae al
    periodo objetivo de la preinscripción.
    """
    from .preinscripcion import periodo_objetivo_actual

    if usuario is not None:
        if rol == "DOCENTE":
            oferta = (OfertaCupo.objects
                      .filter(materia__docentes=usuario)
                      .order_by("-periodo").first())
        else:
            oferta = (OfertaCupo.objects
                      .filter(inscripciones__estudiante=usuario,
                              inscripciones__estado=Inscripcion.Estado.ACTIVA)
                      .order_by("-periodo").first())
        if oferta:
            return oferta.periodo
    return periodo_objetivo_actual()


def horario_de(usuario, rol, periodo=None, solo_materia=None):
    """Punto de entrada: arma el calendario completo según el rol.

    `solo_materia` filtra por código de materia (el dropdown del encabezado).
    """
    if rol == "DOCENTE":
        todos = bloques_docente(usuario, periodo)
    else:
        todos = bloques_estudiante(usuario, periodo)
        # Las preinscripciones (siempre del periodo objetivo) se muestran
        # como bloques preliminares junto al horario confirmado.
        from .preinscripcion import periodo_objetivo_actual
        todos += bloques_preinscripcion(usuario, periodo_objetivo_actual())

    colisiones = calcular_colision([b for b in todos if not b["preliminar"]])
    materias = sorted({(b["materia"].codigo, b["materia"].nombre) for b in todos})
    bloques = todos
    if solo_materia:
        bloques = [b for b in todos if b["materia"].codigo == solo_materia]

    return {
        "bloques": bloques,
        "filas": construir_rejilla(bloques),
        "dias": DIAS_SEMANA,
        "hora_inicio": HORA_INICIO,
        "hora_fin": HORA_FIN,
        "resumen": resumen_horario(bloques, rol),
        "colisiones": colisiones,
        "materias": materias,
    }
