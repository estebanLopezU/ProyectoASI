# =====================================================================
# App anuncios: cartelera institucional (publican docentes y staff).
# =====================================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from comun.mixins import requiere_rol, rol_usuario
from comun.models import AuditoriaLog

from .forms import AnuncioForm
from .models import Anuncio

ROLES_PUBLICAN = ("DOCENTE", "SECRETARIA", "DEPARTAMENTO", "ADMIN")


@login_required
def lista(request):
    """Cartelera visible según el rol (todos los roles ven)."""
    anuncios = Anuncio.visibles(rol=rol_usuario(request.user))
    puede_publicar = rol_usuario(request.user) in ROLES_PUBLICAN or request.user.is_superuser
    return render(request, "anuncios/lista.html", {
        "anuncios": anuncios,
        "puede_publicar": puede_publicar,
    })


@login_required
@requiere_rol("DOCENTE", "SECRETARIA", "DEPARTAMENTO", "ADMIN")
def crear(request):
    if request.method == "POST":
        form = AnuncioForm(request.POST, request.FILES)
        if form.is_valid():
            anuncio = form.save(commit=False)
            anuncio.creado_por = request.user
            anuncio.save()
            AuditoriaLog.registrar(request, "ANUNCIO_CREADO", anuncio, anuncio.titulo)
            messages.success(request, "Anuncio publicado en la cartelera.")
            return redirect("anuncios:lista")
    else:
        form = AnuncioForm()
    return render(request, "anuncios/form.html", {"form": form, "accion": "Publicar"})


@login_required
@requiere_rol("DOCENTE", "SECRETARIA", "DEPARTAMENTO", "ADMIN")
def editar(request, pk):
    anuncio = get_object_or_404(Anuncio, pk=pk)
    # Solo el autor o el staff puede editar.
    if anuncio.creado_por != request.user and rol_usuario(request.user) not in (
            "SECRETARIA", "DEPARTAMENTO", "ADMIN") and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Solo el autor o el personal administrativo puede editar.")
    if request.method == "POST":
        form = AnuncioForm(request.POST, request.FILES, instance=anuncio)
        if form.is_valid():
            form.save()
            AuditoriaLog.registrar(request, "ANUNCIO_EDITADO", anuncio, anuncio.titulo)
            messages.success(request, "Anuncio actualizado.")
            return redirect("anuncios:lista")
    else:
        form = AnuncioForm(instance=anuncio)
    return render(request, "anuncios/form.html", {"form": form, "accion": "Guardar"})


@login_required
@requiere_rol("DOCENTE", "SECRETARIA", "DEPARTAMENTO", "ADMIN")
def desactivar(request, pk):
    anuncio = get_object_or_404(Anuncio, pk=pk)
    if anuncio.creado_por != request.user and rol_usuario(request.user) not in (
            "SECRETARIA", "DEPARTAMENTO", "ADMIN") and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Solo el autor o el personal administrativo puede retirar.")
    if request.method == "POST":
        anuncio.activo = False
        anuncio.save(update_fields=["activo"])
        AuditoriaLog.registrar(request, "ANUNCIO_RETIRADO", anuncio, anuncio.titulo)
        messages.success(request, "Anuncio retirado de la cartelera.")
    return redirect("anuncios:lista")

