# =====================================================================
# Autenticación (RF-01) y perfil (RF-02/RF-03)
# =====================================================================
import json
import time
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from comun.mixins import rol_usuario
from .forms import PerfilForm
from .models import Usuario

# Claves oficiales de prueba de Google: siempre pasan sin llamar a Google.
# Útiles para desarrollo/tests: https://developers.google.com/recaptcha/docs/faq
CLAVES_PRUEBA_GOOGLE = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"


def verificar_recaptcha(token, ip=None):
    """Valida el token de reCAPTCHA v2 invisible contra Google.

    Devuelve (ok, motivo). En modo desarrollo (sin claves) u omite la
    verificación para no bloquear el login local. Con las claves de
    prueba de Google se acepta directamente.
    """
    secreto = getattr(settings, "RECAPTCHA_SECRET_KEY", "")
    if not secreto:
        return True, "modo-desarrollo-sin-claves"
    if secreto.startswith(CLAVES_PRUEBA_GOOGLE[:8]):
        return True, "claves-de-prueba"
    if not token:
        return False, "sin-token"
    datos = {"secret": secreto, "response": token}
    if ip:
        datos["remoteip"] = ip
    try:
        peticion = urllib.request.Request(
            "https://www.google.com/recaptcha/api/siteverify",
            data=urllib.parse.urlencode(datos).encode(),
            headers={"User-Agent": "SGDIC/1.0"},
        )
        with urllib.request.urlopen(peticion, timeout=8) as respuesta:
            resultado = json.loads(respuesta.read().decode())
        if resultado.get("success"):
            return True, "ok"
        return False, ",".join(resultado.get("error-codes", ["fallo"] ))
    except Exception as exc:  # Sin internet: no bloquear, registrar motivo
        return False, f"error-red:{exc}"


def intentos_login(request):
    """Contador de fallos en sesión: {'fallos': int, 'bloqueado_hasta': ts}."""
    return request.session.get("login_intentos", {"fallos": 0, "bloqueado_hasta": 0})


def registrar_fallo(request):
    estado = dict(intentos_login(request))
    estado["fallos"] = estado.get("fallos", 0) + 1
    if estado["fallos"] >= getattr(settings, "LOGIN_MAX_INTENTOS", 3):
        estado["bloqueado_hasta"] = time.time() + getattr(
            settings, "LOGIN_BLOQUEO_SEGUNDOS", 300)
    request.session["login_intentos"] = estado
    return estado


def limpiar_intentos(request):
    request.session.pop("login_intentos", None)


@method_decorator(never_cache, name="dispatch")
class LoginView(auth_views.LoginView):
    template_name = "usuario/login.html"
    # Si ya hay sesión (ej. botón "atrás" del navegador), ir al tablero
    # en vez de mostrar de nuevo el formulario (RF-01).
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        estado = intentos_login(self.request)
        bloqueado_hasta = estado.get("bloqueado_hasta", 0)
        contexto["login_bloqueado"] = time.time() < bloqueado_hasta
        contexto["login_bloqueo_seg"] = max(0, int(bloqueado_hasta - time.time()))
        contexto["login_intentos"] = estado.get("fallos", 0)
        contexto["login_max_intentos"] = getattr(settings, "LOGIN_MAX_INTENTOS", 3)
        contexto["recaptcha_site_key"] = getattr(settings, "RECAPTCHA_SITE_KEY", "")
        return contexto

    def post(self, request, *args, **kwargs):
        estado = intentos_login(request)
        if time.time() < estado.get("bloqueado_hasta", 0):
            # Bloqueado por 3 fallos: volver al login sin validar.
            form = self.get_form(self.get_form_class())
            form.add_error(
                None,
                "Cuenta bloqueada temporalmente por demasiados intentos. "
                "Espere 5 minutos e inténtelo de nuevo.",
            )
            return self.form_invalid(form)
        ok_captcha, _motivo = verificar_recaptcha(
            request.POST.get("g-recaptcha-response", ""),
            request.META.get("REMOTE_ADDR"),
        )
        if not ok_captcha:
            form = self.get_form(self.get_form_class())
            form.add_error(None, "Verificación anti-robots fallida. Inténtelo de nuevo.")
            registrar_fallo(request)
            return self.form_invalid(form)
        respuesta = super().post(request, *args, **kwargs)
        if self.request.user.is_authenticated:
            limpiar_intentos(request)
        else:
            # Fallo de credenciales: actualizar el contador Y el contexto ya
            # renderizado (super().post renderizó con el valor anterior).
            nuevo = registrar_fallo(request)
            try:
                respuesta.context_data["login_intentos"] = nuevo.get("fallos", 0)
                bloqueado = time.time() < nuevo.get("bloqueado_hasta", 0)
                respuesta.context_data["login_bloqueado"] = bloqueado
                respuesta.context_data["login_bloqueo_seg"] = max(
                    0, int(nuevo.get("bloqueado_hasta", 0) - time.time()))
            except Exception:
                pass
        return respuesta


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


@require_POST
@login_required
def ping_sesion(request):
    """Latido de sesión por inactividad.

    El botón "Mantener la sesión abierta" del aviso rojo lo invoca vía
    fetch POST. Al pasar por SessionMiddleware con
    SESSION_SAVE_EVERY_REQUEST=True, Django renueva el vencimiento de la
    cookie (2 min + 30 s), reiniciando el conteo sin recargar la página.
    """
    return JsonResponse({"ok": True})


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
