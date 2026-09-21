# =====================================================================
# Servicio de generación y exportación de reportes (RF-43 a RF-47)
# =====================================================================
import csv
import io


def _filas_ocupacion(parametros):
    """RF-43: ocupación y disponibilidad de cupos."""
    from cupos.models import OfertaCupo

    qs = OfertaCupo.objects.select_related("materia")
    if parametros.get("periodo"):
        qs = qs.filter(periodo=parametros["periodo"])
    filas = [["Materia", "Periodo", "Cupo máximo", "Inscritos", "Disponibles",
              "Ocupación %"]]
    for oferta in qs:
        filas.append([str(oferta.materia), oferta.periodo, oferta.cupo_maximo,
                      oferta.inscritos, oferta.cupos_disponibles,
                      round(oferta.tasa_ocupacion * 100, 1)])
    return filas


def _filas_inasistencia(parametros):
    """RF-25/RF-43: porcentajes de inasistencia por estudiante."""
    from evaluaciones.models import ResumenInasistencia

    qs = ResumenInasistencia.objects.select_related("estudiante", "oferta__materia")
    if parametros.get("min_porcentaje"):
        qs = qs.filter(porcentaje__gte=parametros["min_porcentaje"])
    filas = [["Estudiante", "Materia", "Periodo", "Faltas", "Sesiones",
              "Porcentaje", "Riesgo"]]
    for r in qs:
        filas.append([str(r.estudiante), str(r.oferta.materia), r.oferta.periodo,
                      r.faltas, r.total_sesiones, r.porcentaje,
                      r.get_riesgo_display().upper()])
    return filas


def _filas_quejas(parametros):
    """RF-43/RF-49: tiempos de respuesta y estado de las quejas."""
    from quejas.models import Queja

    qs = Queja.objects.select_related("categoria", "gestor")
    if parametros.get("desde"):
        qs = qs.filter(creada__date__gte=parametros["desde"])
    if parametros.get("hasta"):
        qs = qs.filter(creada__date__lte=parametros["hasta"])
    filas = [["Consecutivo", "Categoría", "Estado", "Prioridad", "Gestor",
              "Radicada", "Horas hasta resolución"]]
    for q in qs:
        horas = round((q.resuelta - q.creada).total_seconds() / 3600, 1) if q.resuelta else ""
        filas.append([q.consecutivo, q.categoria.nombre, q.get_estado_display(),
                      q.get_prioridad_display(), str(q.gestor or "Sin asignar"),
                      q.creada.strftime("%Y-%m-%d %H:%M"), horas])
    return filas


def _filas_evaluacion(parametros):
    """RF-32/RF-43: resultados consolidados de evaluación docente (RN-05)."""
    from django.db.models import Avg, Count

    from evaluaciones.models import RespuestaEvaluacion

    grupo = RespuestaEvaluacion.objects.values(
        "docente__username", "materia__nombre", "periodo__nombre").annotate(
        promedio=Avg("puntuacion"), total=Count("id")).order_by("-promedio")
    minimo = parametros.get("min_respuestas", 5)
    filas = [["Docente", "Materia", "Periodo", "Respuestas", "Promedio", "Publicable"]]
    for g in grupo:
        publicable = g["total"] >= minimo
        filas.append([g["docente__username"], g["materia__nombre"], g["periodo__nombre"],
                      g["total"], round(g["promedio"], 2) if publicable else "n/d",
                      "Sí" if publicable else "No (RN-05)"])
    return filas


def _filas_solicitudes(parametros):
    """RF-06/RF-43: trazabilidad de solicitudes de cupo."""
    from cupos.models import SolicitudCupo

    qs = SolicitudCupo.objects.select_related("estudiante", "oferta__materia")
    if parametros.get("estado"):
        qs = qs.filter(estado=parametros["estado"])
    filas = [["Estudiante", "Materia", "Periodo", "Estado", "Prioridad",
              "Justificación", "Creada"]]
    for s in qs:
        filas.append([str(s.estudiante), str(s.oferta.materia), s.oferta.periodo,
                      s.get_estado_display(), s.prioridad, s.justificacion_estado,
                      s.creada.strftime("%Y-%m-%d %H:%M")])
    return filas


def _filas_mensajeria(parametros):
    """RF-19/RF-43: hilos y tiempos de respuesta."""
    from mensajes.models import Hilo

    filas = [["Asunto", "Estudiante", "Docente", "Tipo", "Mensajes",
              "Horas sin respuesta", "Cerrado"]]
    for hilo in Hilo.objects.select_related("estudiante", "docente"):
        filas.append([hilo.asunto, str(hilo.estudiante), str(hilo.docente),
                      hilo.get_tipo_display(), hilo.mensajes.count(),
                      round(hilo.horas_sin_respuesta(), 1),
                      "Sí" if hilo.cerrado else "No"])
    return filas


def _filas_academico(parametros):
    """RF-43: resumen académico por estudiante."""
    from cupos.models import Inscripcion

    inscripciones = list(Inscripcion.objects.select_related("estudiante"))
    estudiantes = {i.estudiante for i in inscripciones}
    filas = [["Estudiante", "Promedio", "Semestre", "Inscripciones activas"]]
    for estudiante in estudiantes:
        activas = sum(1 for i in inscripciones if i.estudiante_id == estudiante.pk
                      and i.estado == Inscripcion.Estado.ACTIVA)
        filas.append([str(estudiante), float(estudiante.promedio), estudiante.semestre,
                      activas])
    return filas


GENERADORES = {
    "OCUPACION": _filas_ocupacion,
    "INASISTENCIA": _filas_inasistencia,
    "QUEJAS": _filas_quejas,
    "EVALUACION": _filas_evaluacion,
    "SOLICITUDES": _filas_solicitudes,
    "MENSAJERIA": _filas_mensajeria,
    "ACADEMICO": _filas_academico,
}


def generar_filas(tipo, parametros=None):
    """Devuelve la matriz de datos del tipo de reporte solicitado."""
    generador = GENERADORES.get(tipo)
    if not generador:
        raise ValueError(f"Tipo de reporte no soportado: {tipo}")
    return generador(parametros or {})


def exportar_csv(filas):
    """RF-45: exportación CSV (delimitador ';' para Excel en español)."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    escritor.writerows(filas)
    return buffer.getvalue()


def exportar_xlsx(filas, titulo="Reporte"):
    """RF-45: exportación Excel con openpyxl (dependencia opcional)."""
    try:
        from openpyxl import Workbook
    except ImportError:
        return None
    libro = Workbook()
    hoja = libro.active
    hoja.title = titulo[:30]
    for fila in filas:
        hoja.append(list(fila))
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def exportar_pdf(filas, titulo="Reporte SGDIC"):
    """RF-45: exportación PDF con reportlab (dependencia opcional)."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    except ImportError:
        return None
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=letter, title=titulo)
    tabla = Table([list(f) for f in filas], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    documento.build([tabla])
    return buffer.getvalue()


def exportar(filas, formato="CSV"):
    """Despacha al exportador correspondiente; devuelve bytes."""
    if formato == "XLSX":
        datos = exportar_xlsx(filas)
        return datos if datos is not None else exportar_csv(filas).encode("utf-8")
    if formato == "PDF":
        datos = exportar_pdf(filas)
        return datos if datos is not None else exportar_csv(filas).encode("utf-8")
    return exportar_csv(filas).encode("utf-8")

