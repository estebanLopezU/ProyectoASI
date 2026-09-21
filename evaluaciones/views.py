# =====================================================================
# Vistas de evaluaciones: faltas/justificaciones (RF-21 a RF-26) y
# evaluación docente anónima (RF-27 a RF-34)
# =====================================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comun.mixins import requiere_rol, rol_usuario
from comun.models import Notificacion
from cupos.models import OfertaCupo
from .forms import (JustificacionForm, PeriodoEvaluacionForm, RegistroFaltasForm,
                    RespuestaEvaluacionForm, RevisionJustificacionForm, SesionForm)
from .models import (Falta, InvitacionEvaluacion, PeriodoEvaluacion,
                     ResumenInasistencia, RespuestaEvaluacion, Sesion)


# ------------------------- Faltas (RF-21 a RF-26) -------------------------
def _recalcular_resumen(falta):
    """Actualiza el acumulado de inasistencia y dispara alertas (RF-25/RF-26)."""
    resumen, _ = ResumenInasistencia.objects.get_or_create(
        estudiante=falta.estudiante, oferta=falta.sesion.oferta)
    resumen.calcular()
    resumen.alertar_si_corresponde()
    return resumen


@login_required
def mis_faltas(request):
    """RF-21/RF-23: el estudiante consulta y justifica sus faltas."""
    faltas = Falta.objects.filter(estudiante=request.user).select_related(
        "sesion__oferta__materia")
    resumenes = ResumenInasistencia.objects.filter(
        estudiante=request.user).select_related("oferta__materia")
    return render(request, "evaluaciones/mis_faltas.html",
                  {"faltas": faltas, "resumenes": resumenes})


@login_required
def justificar_falta(request, pk):
    """RF-23: adjuntar justificación con evidencia."""
    falta = get_object_or_404(Falta, pk=pk, estudiante=request.user)
    if falta.estado == Falta.Estado.JUSTIFICADA:
        messages.info(request, "La falta ya está justificada.")
        return redirect("evaluaciones:mis_faltas")
    if request.method == "POST":
        form = JustificacionForm(request.POST, request.FILES, instance=falta)
        if form.is_valid():
            falta.comentario_justificacion = form.cleaned_data["comentario_justificacion"]
            falta.evidencia = form.cleaned_data.get("evidencia")
            falta.save()
            falta.justificar(falta.comentario_justificacion)
            messages.success(request, "Justificación enviada al docente.")
            return redirect("evaluaciones:mis_faltas")
    else:
        form = JustificacionForm(instance=falta)
    return render(request, "evaluaciones/justificar.html", {"form": form, "falta": falta})


@requiere_rol("DOCENTE", "SECRETARIA", "DEPARTAMENTO")
def revisar_justificaciones(request):
    """RF-24: bandeja de justificaciones pendientes."""
    if request.method == "POST":
        falta = get_object_or_404(Falta, pk=request.POST.get("falta"))
        falta.revisar(aprobada=request.POST.get("aprobada") == "1",
                      comentario=request.POST.get("comentario", ""))
        _recalcular_resumen(falta)
        messages.success(request, "Justificación revisada.")
        return redirect("evaluaciones:revisar_lista")
    pendientes = Falta.objects.exclude(comentario_justificacion="").filter(
        estado=Falta.Estado.REGISTRADA
    ).select_related("estudiante", "sesion__oferta__materia")
    if rol_usuario(request.user) == "DOCENTE":
        pendientes = pendientes.filter(sesion__oferta__materia__docentes=request.user)
    return render(request, "evaluaciones/revisar.html", {"pendientes": pendientes.distinct()})


@requiere_rol("DOCENTE", "SECRETARIA", "DEPARTAMENTO")
def revisar_falta(request, pk):
    falta = get_object_or_404(Falta, pk=pk)
    if request.method == "POST":
        form = RevisionJustificacionForm(request.POST)
        if form.is_valid():
            falta.revisar(form.cleaned_data["aprobada"], form.cleaned_data["comentario"])
            _recalcular_resumen(falta)
            messages.success(request, "Falta actualizada.")


@requiere_rol("DOCENTE", "SECRETARIA", "DEPARTAMENTO")
def registrar_asistencia(request, pk=None):
    """RF-21: registrar asistencia de una sesión de clase."""
    ofertas = OfertaCupo.objects.filter(activa=True)
    if rol_usuario(request.user) == "DOCENTE":
        ofertas = ofertas.filter(materia__docentes=request.user).distinct()
    if request.method == "POST" and "crear_sesion" in request.POST:
        form_sesion = SesionForm(request.POST)
        if form_sesion.is_valid():
            sesion, creada = Sesion.objects.get_or_create(
                oferta_id=request.POST.get("oferta"),
                fecha=form_sesion.cleaned_data["fecha"],
                defaults={"tema": form_sesion.cleaned_data["tema"]},
            )
            messages.success(request, "Sesión creada." if creada else "La sesión ya existía.")
            return redirect("evaluaciones:asistencia_sesion", sesion.pk)
    sesion = get_object_or_404(Sesion, pk=pk) if pk else None
    if sesion and request.method == "POST":
        form = RegistroFaltasForm(request.POST, oferta=sesion.oferta)
        if form.is_valid():
            ausentes = form.cleaned_data["ausentes"]
            for estudiante in ausentes:
                falta, creada = Falta.objects.get_or_create(
                    sesion=sesion, estudiante=estudiante,
                    defaults={"motivo": form.cleaned_data["motivo"]},
                )
                if creada:
                    falta.notificar()  # RF-22/RN-07
                    _recalcular_resumen(falta)
            sesion.registrada = True
            sesion.save(update_fields=["registrada"])
            messages.success(request, f"Asistencia registrada ({len(ausentes)} ausentes).")
            return redirect("evaluaciones:registrar_asistencia")
    elif sesion:
        form = RegistroFaltasForm(oferta=sesion.oferta)
    else:
        form = None
    return render(request, "evaluaciones/asistencia.html", {
        "sesion": sesion, "form": form, "form_sesion": SesionForm(),
        "sesiones": Sesion.objects.select_related("oferta__materia")[:30],
        "ofertas": ofertas,
    })


@requiere_rol("DOCENTE", "SECRETARIA", "DEPARTAMENTO")
def panel_inasistencia(request):
    """RF-25/RF-26: panel de porcentajes de inasistencia con semáforo."""
    resumenes = ResumenInasistencia.objects.select_related(
        "estudiante", "oferta__materia").order_by("-porcentaje")
    if rol_usuario(request.user) == "DOCENTE":
        resumenes = resumenes.filter(oferta__materia__docentes=request.user).distinct()
    criticos = resumenes.filter(riesgo=ResumenInasistencia.Riesgo.CRITICO).count()
    return render(request, "evaluaciones/panel_inasistencia.html", {
        "resumenes": resumenes, "criticos": criticos,
        "umbral": request.sgdic_config["umbral_inasistencia"],
    })


# ------------------- Evaluación docente (RF-27 a RF-34) -------------------
def _periodo_vigente():
    return PeriodoEvaluacion.objects.filter(
        activo=True, fecha_inicio__lte=timezone.localdate(),
        fecha_limite__gte=timezone.localdate(),
    ).order_by("-fecha_inicio").first()


@login_required
def mis_invitaciones(request):
    """RF-28/RF-29: el estudiante ve sus evaluaciones pendientes."""
    periodo = _periodo_vigente()
    invitaciones = InvitacionEvaluacion.objects.filter(
        estudiante=request.user).select_related("docente", "materia", "periodo")
    pendientes = invitaciones.filter(completada=False,
                                     periodo__fecha_limite__gte=timezone.localdate())
    return render(request, "evaluaciones/mis_invitaciones.html", {
        "periodo": periodo, "invitaciones": invitaciones, "pendientes": pendientes,
    })


@login_required
def responder_evaluacion(request, pk):
    """RF-30/RN-05: respuesta anónima; nunca se almacena el autor."""
    invitacion = get_object_or_404(InvitacionEvaluacion, pk=pk, estudiante=request.user)
    if invitacion.completada:
        messages.info(request, "Ya respondió esta evaluación.")
        return redirect("evaluaciones:mis_invitaciones")
    if not invitacion.periodo.activo:
        messages.warning(request, "El periodo de evaluación no está habilitado (RN-06).")
        return redirect("evaluaciones:mis_invitaciones")
    preguntas = invitacion.periodo.preguntas_activas()
    if request.method == "POST":
        form = RespuestaEvaluacionForm(request.POST, preguntas=preguntas)
        if form.is_valid():
            RespuestaEvaluacion.objects.create(
                periodo=invitacion.periodo, docente=invitacion.docente,
                materia=invitacion.materia, puntuacion=form.promedio(),
                comentario=form.cleaned_data.get("comentario", ""),
                respuestas_detalle={f"p{i}": v for i, v in enumerate(form.puntuaciones())},
            )
            invitacion.completada = True
            invitacion.save(update_fields=["completada"])
            messages.success(request, "Evaluación registrada de forma anónima. ¡Gracias!")
            return redirect("evaluaciones:mis_invitaciones")
    else:
        form = RespuestaEvaluacionForm(preguntas=preguntas)
    return render(request, "evaluaciones/responder.html",
                  {"form": form, "invitacion": invitacion})


@requiere_rol("DOCENTE", "SECRETARIA", "DEPARTAMENTO", "ADMIN")
def resultados_docente(request):
    """RF-32/RF-33: resultados consolidados respetando el anonimato (RN-05)."""
    from usuario.models import Usuario

    minimo = request.sgdic_config["min_respuestas_anonimo"]
    if rol_usuario(request.user) == "DOCENTE":
        docente = request.user
    else:
        docente = Usuario.objects.filter(pk=request.GET.get("docente"), rol="DOCENTE").first()
    resumenes = []
    if docente:
        grupos = RespuestaEvaluacion.objects.filter(docente=docente).values(
            "periodo_id", "periodo__nombre", "materia_id", "materia__nombre")
        for grupo in grupos:
            respuestas = RespuestaEvaluacion.objects.filter(
                docente=docente, materia_id=grupo["materia_id"],
                periodo_id=grupo["periodo_id"])
            total = respuestas.count()
            publicable = total >= minimo
            resumenes.append({
                "materia": grupo["materia__nombre"],
                "periodo": grupo["periodo__nombre"],
                "total": total,
                "promedio": round(respuestas.aggregate(p=Avg("puntuacion"))["p"] or 0, 2),
                "publicable": publicable,
                "comentarios": [r.comentario for r in respuestas if r.comentario]
                if publicable else [],
            })
    return render(request, "evaluaciones/resultados.html", {
        "resumenes": resumenes, "docente": docente,
        "docentes": Usuario.objects.filter(rol="DOCENTE"), "minimo": minimo,
    })


@requiere_rol("DEPARTAMENTO", "ADMIN")
def gestionar_periodos(request):
    """RF-27/RF-34: el departamento configura los periodos de evaluación."""
    if request.method == "POST":
        form = PeriodoEvaluacionForm(request.POST)
        if form.is_valid():
            periodo = form.save(commit=False)
            if periodo.activo:
                PeriodoEvaluacion.objects.exclude(pk=periodo.pk).update(activo=False)
            periodo.save()
            creadas = _generar_invitaciones(periodo)
            messages.success(request, f"Periodo guardado. Invitaciones nuevas: {creadas}.")
            return redirect("evaluaciones:periodos")
    else:
        form = PeriodoEvaluacionForm()
    return render(request, "evaluaciones/periodos.html",
                  {"form": form, "periodos": PeriodoEvaluacion.objects.all()})


def _generar_invitaciones(periodo):
    """RF-29: una invitación por estudiante, docente y materia inscrita."""
    from cupos.models import Inscripcion

    creadas = 0
    inscripciones = Inscripcion.objects.filter(
        estado=Inscripcion.Estado.ACTIVA).select_related("oferta__materia")
    for inscripcion in inscripciones:
        materia = inscripcion.oferta.materia
        for docente in materia.docentes.all():
            _, creada = InvitacionEvaluacion.objects.get_or_create(
                periodo=periodo, estudiante=inscripcion.estudiante,
                docente=docente, materia=materia)
            creadas += int(creada)
    return creadas


@requiere_rol("DEPARTAMENTO", "ADMIN", "SECRETARIA")
def enviar_recordatorios(request, pk):
    """RF-29: recordatorio a quienes no han respondido."""
    periodo = get_object_or_404(PeriodoEvaluacion, pk=pk)
    pendientes = periodo.invitaciones.filter(completada=False)
    for invitacion in pendientes:
        Notificacion.enviar(
            invitacion.estudiante,
            "Recordatorio: evaluación docente pendiente",
            f"Aún no ha evaluado a {invitacion.docente} en {invitacion.materia}. "
            f"Plazo: {periodo.fecha_limite}.",
            url="/evaluaciones/evaluacion/",
            nivel=Notificacion.Nivel.ADVERTENCIA,
        )
        invitacion.recordatorio_enviado = timezone.now()
        invitacion.save(update_fields=["recordatorio_enviado"])
    messages.success(request, f"Recordatorios enviados a {pendientes.count()} estudiantes.")
    return redirect("evaluaciones:periodos")

