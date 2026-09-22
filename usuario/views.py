# =====================================================================
# Autenticación (RF-01) y perfil (RF-02/RF-03)
# =====================================================================
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render

from comun.mixins import rol_usuario
from .forms import PerfilForm
from .models import Usuario


class LoginView(auth_views.LoginView):
    template_name = "usuario/login.html"


class LogoutView(auth_views.LogoutView):
    pass


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "usuario/password_reset.html"
    email_template_name = "usuario/password_reset_email.html"
    subject_template_name = "usuario/password_reset_subject.txt"
    success_url = "password-reset/hecho/"


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "usuario/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "usuario/password_reset_confirm.html"
    success_url = "hecho/"


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "usuario/password_reset_complete.html"


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "usuario/password_change.html"
    success_url = "hecho/"


class PasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "usuario/password_change_done.html"


@login_required
def perfil(request):
    """Consulta y edición del perfil propio."""
    if request.method == "POST":
        form = PerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado correctamente.")
    else:
        form = PerfilForm(instance=request.user)
    return render(request, "usuario/perfil.html", {"form": form})


@login_required
def mallas(request):
    """Listado de estudiantes para consultar y editar su malla curricular.

    Acceso exclusivo del personal administrativo (secretaría, departamento y
    administrador): es el único que puede modificar la malla de un estudiante.
    """
    if rol_usuario(request.user) not in ("SECRETARIA", "DEPARTAMENTO", "ADMIN"):
        raise PermissionDenied("Su rol no tiene acceso a las mallas curriculares.")

    busqueda = request.GET.get("q", "").strip()
    estudiantes = Usuario.objects.filter(rol="ESTUDIANTE")
    if busqueda:
        estudiantes = estudiantes.filter(
            Q(username__icontains=busqueda)
            | Q(first_name__icontains=busqueda)
            | Q(last_name__icontains=busqueda)
            | Q(codigo_institucional__icontains=busqueda)
        )
    estudiantes = estudiantes.order_by("last_name", "first_name", "username")
    return render(request, "usuario/mallas.html", {
        "estudiantes": estudiantes,
        "busqueda": busqueda,
        "total": estudiantes.count(),
    })
