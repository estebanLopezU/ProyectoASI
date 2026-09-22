# =====================================================================
# Cálculo de KPI operativos (RF-49, RF-50) compartidos entre apps
# =====================================================================
from django.db.models import Avg, F
from django.utils import timezone

from comun.models import Notificacion


def kpi_cupos():
    """KPI: ocupación promedio, solicitudes pendientes y listas de espera."""
    from cupos.models import OfertaCupo, SolicitudCupo

    ofertas = OfertaCupo.objects.filter(activa=True)
    return {
        "materias_activas": ofertas.count(),
        "ocupacion_promedio": round(
            ofertas.aggregate(v=Avg(F("inscritos") * 100.0 / F("cupo_maximo")))["v"] or 0, 1
        ),
        "solicitudes_pendientes": SolicitudCupo.objects.filter(
            estado=SolicitudCupo.Estado.PENDIENTE).count(),
        "en_espera": SolicitudCupo.objects.filter(
            estado=SolicitudCupo.Estado.EN_ESPERA).count(),
    }


def kpi_quejas():
    """KPI: abiertos, en proceso, escalados y tiempo medio de cierre (RF-49)."""
    from quejas.models import Queja

    casos = Queja.objects.all()
    resueltas = [q for q in casos if q.resuelta]
    horas = [(q.resuelta - q.creada).total_seconds() / 3600 for q in resueltas]
    escaladas = casos.filter(estado=Queja.Estado.ESCALADO).count()
    return {
        "abiertos": casos.filter(estado=Queja.Estado.ABIERTO).count(),
        "en_proceso": casos.filter(estado=Queja.Estado.EN_PROCESO).count(),
        "escalados": escaladas,
        "resueltos": casos.filter(
            estado__in=(Queja.Estado.RESUELTO, Queja.Estado.CERRADO)).count(),
        "horas_promedio_cierre": round(sum(horas) / len(horas), 1) if horas else 0,
        "satisfaccion_promedio": round(
            casos.aggregate(v=Avg("satisfaccion"))["v"] or 0, 2),
    }



def kpi_evaluaciones():
    """KPI: participación docente y puntaje promedio (anonimizado RN-05)."""
    from evaluaciones.models import PeriodoEvaluacion, RespuestaEvaluacion

    activo = PeriodoEvaluacion.objects.filter(activo=True).first()
    if not activo:
        return {"participacion": 0, "puntaje_promedio": 0, "respuestas": 0}
    inv = activo.invitaciones.count()
    resp = RespuestaEvaluacion.objects.filter(periodo=activo).count()
    puntaje = RespuestaEvaluacion.objects.filter(periodo=activo).aggregate(
        p=Avg("puntuacion"))["p"] or 0
    return {
        "participacion": round(resp * 100.0 / inv, 1) if inv else 0,
        "puntaje_promedio": round(puntaje, 2),
        "respuestas": resp,
    }


def kpi_inasistencia():
    """KPI: estudiantes con inasistencia en riesgo (RF-25)."""
    from evaluaciones.models import ResumenInasistencia

    resumenes = ResumenInasistencia.objects.all()
    return {
        "en_riesgo": resumenes.filter(
            riesgo=ResumenInasistencia.Riesgo.CRITICO).count(),
        "advertencia": resumenes.filter(
            riesgo=ResumenInasistencia.Riesgo.ADVERTENCIA).count(),
        "porcentaje_promedio": round(
            resumenes.aggregate(v=Avg("porcentaje"))["v"] or 0, 2),
    }


def kpi_solicitudes():
    """KPI: solicitudes de materias nuevas pendientes de revisión."""
    from materias.models import Materia, SolicitudMateria

    pendientes = (Materia.Estado.PROPUESTA, Materia.Estado.EN_REVISION)
    qs = SolicitudMateria.objects.all()
    return {
        "pendientes": qs.filter(estado__in=pendientes).count(),
        "aprobadas": qs.filter(estado=Materia.Estado.APROBADA).count(),
        "total": qs.count(),
    }



def kpi_mensajes():
    """KPI: mensajes sin respuesta y tiempo medio de respuesta (RF-19)."""
    from mensajes.models import Hilo

    sin_respuesta = 0
    horas = []
    for hilo in Hilo.objects.prefetch_related("mensajes__autor"):
        if hilo.horas_sin_respuesta() > 0:
            sin_respuesta += 1
        primera = hilo.mensajes.first()
        if not primera:
            continue
        respuesta = hilo.mensajes.exclude(pk=primera.pk).first()
        if respuesta:
            horas.append((respuesta.creado - primera.creado).total_seconds() / 3600)
    return {
        "sin_respuesta": sin_respuesta,
        "horas_promedio_respuesta": round(sum(horas) / len(horas), 1) if horas else 0,
    }


def mensajes_model():
    from mensajes.models import Mensaje

    return Mensaje


def notificaciones_no_leidas(user):
    if not user or not user.is_authenticated:
        return 0
    return Notificacion.objects.filter(destinatario=user, leida=False).count()


def tablero_kpis(usuario=None):
    """RF-50: consolidado de KPIs para el tablero inicial según el rol."""
    from comun.mixins import rol_usuario

    rol = rol_usuario(usuario)
    datos = {
        "notificaciones": notificaciones_no_leidas(usuario),
        "actualizado": timezone.now(),
    }
    if rol == "ESTUDIANTE":
        from cupos.models import Inscripcion
        from cupos.preinscripcion import periodo_objetivo_actual, resumen_preinscripcion
        from evaluaciones.models import InvitacionEvaluacion

        datos.update({
            "inscripciones_activas": Inscripcion.objects.filter(
                estudiante=usuario, estado=Inscripcion.Estado.ACTIVA).count(),
            "evaluaciones_pendientes": InvitacionEvaluacion.objects.filter(
                estudiante=usuario, completada=False).count(),
            "preinscripcion": resumen_preinscripcion(usuario, periodo_objetivo_actual()),
        })
    elif rol == "DOCENTE":
        from evaluaciones.models import RespuestaEvaluacion
        from mensajes.models import Hilo

        datos.update({
            "hilos_activos": Hilo.objects.filter(docente=usuario, cerrado=False).count(),
            "puntaje_promedio": round(
                RespuestaEvaluacion.objects.filter(docente=usuario).aggregate(
                    v=Avg("puntuacion"))["v"] or 0, 2),
        })
        from cupos.models import OfertaCupo

        ofertas = OfertaCupo.objects.filter(materia__docentes=usuario).distinct()
        datos.update({
            "materias_dictadas": ofertas.values("materia").distinct().count(),
            "horas_semanales": round(sum(
                (o.hora_fin.hour * 60 + o.hora_fin.minute)
                - (o.hora_inicio.hour * 60 + o.hora_inicio.minute)
                for o in ofertas) / 60, 1),
        })
    elif rol in ("SECRETARIA", "DEPARTAMENTO", "ADMIN"):
        datos.update(kpi_cupos())
        datos.update(kpi_quejas())
        datos.update(kpi_evaluaciones())
        datos.update(kpi_inasistencia())
        datos.update(kpi_solicitudes())
    return datos
