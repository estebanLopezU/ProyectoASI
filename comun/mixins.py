# =====================================================================
# RBAC: mixins de acceso por rol (RF-02) y decoradores
# =====================================================================
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.decorators import method_decorator

ROLES_STAFF = ("SECRETARIA", "DEPARTAMENTO", "ADMIN")


def rol_usuario(user):
    """Devuelve el rol del usuario o None."""
    if not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "rol", None) or "ADMIN"


def requiere_rol(*roles):
    """Decorador: exige sesión iniciada y pertenecer a alguno de los roles."""

    def decorador(view):
        def envoltura(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect("usuario:login")
            rol = rol_usuario(user)
            if rol == "ADMIN" or rol in roles:
                return view(request, *args, **kwargs)
            raise PermissionDenied("Su rol no tiene acceso a este módulo.")

        return envoltura

    return decorador


def es_staff(user):
    return rol_usuario(user) in ROLES_STAFF


class MixinRol:
    """Mixin CBV: exige sesión y rol (usa `roles_permitidos` en la vista)."""

    roles_permitidos: tuple = ()

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        rol = rol_usuario(request.user)
        if rol != "ADMIN" and (not self.roles_permitidos or rol not in self.roles_permitidos):
            raise PermissionDenied("Su rol no tiene acceso a este módulo.")
        return super().dispatch(request, *args, **kwargs)


class MixinStaff(MixinRol):
    """Acceso exclusivo para Secretaría / Departamento / Admin."""

    roles_permitidos = ROLES_STAFF
