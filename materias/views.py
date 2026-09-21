# =====================================================================
# Vistas de materias (RF-11 a RF-15)
# =====================================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from comun.mixins import MixinRol
from .forms import SolicitudMateriaForm
from .models import Materia, SolicitudMateria


class CatalogoView(ListView):
    """Catálogo público de materias publicadas (RF-15)."""

    template_name = "materias/catalogo.html"
    context_object_name = "materias"
    paginate_by = 15

    def get_queryset(self):
        q = self.request.GET.get("q", "").strip()
        filtro = Q(estado=Materia.Estado.PUBLICADA)
        if q:
            filtro &= Q(nombre__icontains=q) | Q(codigo__icontains=q)
        return Materia.objects.filter(filtro)


@login_required
def proponer_materia(request):
    """RF-11: docente propone crear una materia nueva."""
    if request.method == "POST":
        form = SolicitudMateriaForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                materia = Materia.objects.create(
                    codigo=form.cleaned_data["codigo_nuevo"],
                    nombre=form.cleaned_data["nombre"],
                    creditos=form.cleaned_data["creditos"],
                    cupo_maximo=form.cleaned_data["cupo_maximo"],
                    estado=Materia.Estado.PROPUESTA,
                )
                SolicitudMateria.objects.create(
                    materia=materia,
                    tipo=SolicitudMateria.Tipo.CREACION,
                    justificacion=form.cleaned_data["justificacion"],
                    propuesta={
                        "nombre": form.cleaned_data["nombre"],
                        "creditos": form.cleaned_data["creditos"],
                        "cupo_maximo": form.cleaned_data["cupo_maximo"],
                    },
                    solicitante=request.user,
                )
            messages.success(request, "Propuesta creada. Quedó en revisión del departamento.")
            return redirect("materias:panel")
    else:
        form = SolicitudMateriaForm()
    return render(request, "materias/proponer.html", {"form": form})


@login_required
def editar_materia(request, pk):
    """RF-12: docente solicita edición de una materia existente."""
    materia = get_object_or_404(Materia, pk=pk)
    if request.method == "POST":
        form = SolicitudMateriaForm(request.POST, materia=materia)
        if form.is_valid():
            with transaction.atomic():
                SolicitudMateria.objects.create(
                    materia=materia,
                    tipo=SolicitudMateria.Tipo.EDICION,
                    justificacion=form.cleaned_data["justificacion"],
                    propuesta=form.propuesta(),
                    solicitante=request.user,
                )
            messages.success(request, "Solicitud de edición enviada al departamento.")
            return redirect("materias:panel")
    else:
        form = SolicitudMateriaForm(materia=materia)
    return render(request, "materias/editar.html", {"form": form, "materia": materia})


class PanelMateriasView(MixinRol, ListView):
    """Panel del departamento: solicitudes pendientes de revisión (RF-13)."""

    roles_permitidos = ("DEPARTAMENTO",)
    template_name = "materias/panel.html"
    context_object_name = "solicitudes"
    paginate_by = 15

    def get_queryset(self):
        return SolicitudMateria.objects.select_related("materia", "solicitante")


@login_required
def revisar_solicitud(request, pk, decision):
    """RF-13: aprobar/rechazar la solicitud (RN-11)."""
    solicitud = get_object_or_404(SolicitudMateria, pk=pk)
    comentario = request.POST.get("comentario", "")
    if decision == "aprobar":
        solicitud.aprobar(request.user)
        messages.success(request, "Solicitud aprobada y materia publicada.")
    elif decision == "rechazar":
        solicitud.rechazar(request.user, comentario)
        messages.warning(request, "Solicitud rechazada.")
    return redirect("materias:panel")
