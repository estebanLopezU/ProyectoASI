# =====================================================================
# Vistas de cupos (RF-05 a RF-10)
# =====================================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView

from comun.mixins import MixinRol, MixinStaff, rol_usuario
from .models import Inscripcion, OfertaCupo, SolicitudCupo


class OfertasView(ListView):
    """RF-05: catálogo de ofertas con disponibilidad en tiempo real."""

    template_name = "cupos/ofertas.html"
    context_object_name = "ofertas"
    paginate_by = 12

    def get_queryset(self):
        qs = OfertaCupo.objects.filter(activa=True).select_related("materia")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(materia__nombre__icontains=q) | Q(materia__codigo__icontains=q))
        return qs


@login_required
def solicitar_cupo(request, oferta_id):
    """RF-05: el estudiante solicita un cupo y el sistema valida (RF-06)."""
    if request.method != "POST":
        return redirect("cupos:ofertas")
    if rol_usuario(request.user) != "ESTUDIANTE":
        messages.error(request, "Solo los estudiantes pueden solicitar cupos.")
        return redirect("cupos:ofertas")
    oferta = get_object_or_404(OfertaCupo, pk=oferta_id, activa=True)
    solicitud, creada = SolicitudCupo.objects.get_or_create(
        oferta=oferta, estudiante=request.user
    )
    if not creada:
        messages.info(request, "Ya tiene una solicitud para esta oferta.")
        return redirect("cupos:mis_solicitudes")
    solicitud.procesar()
    messages.success(
        request, f"Solicitud procesada: {solicitud.get_estado_display()}."
    )
    return redirect("cupos:mis_solicitudes")


class MisSolicitudesView(ListView):
    """RF-08: el estudiante consulta el resultado de sus solicitudes."""

    template_name = "cupos/mis_solicitudes.html"
    context_object_name = "solicitudes"

    def get_queryset(self):
        return (
            SolicitudCupo.objects.filter(estudiante=self.request.user)
            .select_related("oferta", "oferta__materia")
        )


@login_required
def confirmar_cupo(request, inscripcion_id):
    """RF-09: el estudiante confirma la inscripción dentro del plazo."""
    inscripcion = get_object_or_404(
        Inscripcion, pk=inscripcion_id, estudiante=request.user, estado=Inscripcion.Estado.ACTIVA
    )
    inscripcion.confirmada = timezone.now()
    inscripcion.save(update_fields=["confirmada"])
    messages.success(request, "Cupo confirmado.")
    return redirect("cupos:inscripciones")


class MisInscripcionesView(ListView):
    template_name = "cupos/inscripciones.html"
    context_object_name = "inscripciones"

    def get_queryset(self):
        return (
            Inscripcion.objects.filter(estudiante=self.request.user)
            .select_related("oferta", "oferta__materia")
        )


class ListaEsperaView(MixinStaff, ListView):
    """RF-10: secretaría ve y gestiona la lista de espera por materia."""

    template_name = "cupos/lista_espera.html"
    context_object_name = "solicitudes"

    def get_queryset(self):
        qs = SolicitudCupo.objects.select_related("oferta__materia", "estudiante")
        oferta_id = self.request.GET.get("oferta")
        if oferta_id:
            qs = qs.filter(oferta_id=oferta_id)
        return qs.order_by("oferta_id", "-prioridad", "creada")


@login_required
def procesar_pendientes(request):
    """RF-07: procesa solicitudes pendientes respetando la prioridad."""
    if rol_usuario(request.user) not in ("SECRETARIA", "DEPARTAMENTO", "ADMIN"):
        messages.error(request, "No tiene permisos para esta operación.")
        return redirect("dashboard")
    pendientes = SolicitudCupo.objects.filter(estado=SolicitudCupo.Estado.PENDIENTE)
    total = 0
    for solicitud in pendientes.order_by("-prioridad", "creada"):
        solicitud.procesar()
        total += 1
    messages.success(request, f"{total} solicitudes procesadas.")
    return redirect("cupos:lista_espera")
