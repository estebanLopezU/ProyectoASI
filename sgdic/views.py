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
    plantilla = "dashboard.html"
    if rol == "ESTUDIANTE":
        plantilla = "dashboard_estudiante.html"
    elif rol == "DOCENTE":
        plantilla = "dashboard_docente.html"
    elif rol in ("SECRETARIA", "DEPARTAMENTO", "ADMIN"):
        plantilla = "dashboard_admin.html"
    return render(request, plantilla, contexto)


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
