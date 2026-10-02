# =====================================================================
# SGDIC - Tablero principal (dashboard) y vistas transversales
# =====================================================================
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from comun.kpi import tablero_kpis
from comun.mixins import es_staff, rol_usuario
from comun.models import Notificacion


@login_required
def dashboard(request):
    """Tablero inicial según el rol (RF-08/RF-49/RF-50)."""
    rol = rol_usuario(request.user)
    contexto = {
        "rol": rol,
        "es_staff": es_staff(request.user),
        "kpis": tablero_kpis(usuario=request.user),
    }
    contexto.update(_contexto_investigacion(request.user))
    plantilla = "dashboard.html"
    if rol == "ESTUDIANTE":
        plantilla = "dashboard_estudiante.html"
    elif rol == "DOCENTE":
        plantilla = "dashboard_docente.html"
    elif rol in ("SECRETARIA", "DEPARTAMENTO", "ADMIN"):
        plantilla = "dashboard_admin.html"
    return render(request, plantilla, contexto)


def _contexto_investigacion(user):
    """Datos del panel de grupos/semilleros del tablero (visible para todos).

    Mantiene el tablero usable: si la app no está migrada todavía, el panel
    simplemente se omite en vez de romper el tablero completo.
    """
    from investigacion.models import ROLES_INSCRIBEN, ROLES_PUBLICAN, Grupo, Inscripcion

    try:
        grupos = list(
            Grupo.activos().select_related("coordinador")[:4]
        )
        pendientes = Inscripcion.objects.filter(
            grupo__coordinador=user, estado=Inscripcion.Estado.PENDIENTE
        ).count()
    except Exception:  # pragma: no cover - app sin migrar
        return {}
    return {
        "inv_grupos": grupos,
        "inv_pendientes": pendientes,
        "inv_es_coordinador": Grupo.objects.filter(coordinador=user).exists(),
        "inv_puede_publicar": (rol_usuario(user) in ROLES_PUBLICAN
                               or user.is_superuser),
        "inv_puede_inscribirse": rol_usuario(user) in ROLES_INSCRIBEN,
    }


@login_required
def notificaciones(request):
    """RF-08: bandeja de notificaciones del usuario."""
    lista = request.user.notificaciones.all()
    if request.method == "POST":
        if request.POST.get("accion") == "marcar-todas":
            lista.filter(leida=False).update(leida=True)
        marca = request.POST.get("marcar")
        if marca:
            lista.filter(pk=marca).update(leida=True)
        return redirect("notificaciones")
    return render(request, "comun/notificaciones.html",
                  {"notificaciones": lista, "sin_leer": lista.filter(leida=False).count()})


@login_required
def notificacion_ir(request, pk):
    """Marca como leída y redirige al destino de la notificación."""
    notificacion = Notificacion.objects.filter(pk=pk, destinatario=request.user).first()
    if notificacion:
        notificacion.leida = True
        notificacion.save(update_fields=["leida"])
        if notificacion.url:
            return redirect(notificacion.url)
    return redirect("notificaciones")
