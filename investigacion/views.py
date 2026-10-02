# =====================================================================
# App investigacion: grupos de investigación y semilleros.
# Publican: DOCENTE, SECRETARIA, DEPARTAMENTO (ADMIN siempre pasa).
# Ven: todos los roles.
# Se inscriben: solo DOCENTE y ESTUDIANTE, con aprobación del coordinador.
# =====================================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comun.mixins import requiere_rol, rol_usuario
from comun.models import AuditoriaLog, Notificacion

from .forms import GrupoForm, SolicitudForm
from .models import ROLES_INSCRIBEN, ROLES_PUBLICAN, Grupo, Inscripcion


def _puede_publicar(user):
    return rol_usuario(user) in ROLES_PUBLICAN


def _puede_inscribirse(user):
    return rol_usuario(user) in ROLES_INSCRIBEN


def _filas_para(user, grupos):
    """Añade a cada grupo el dato que la plantilla necesita para el botón."""
    propias = {
        i.grupo_id: i
        for i in Inscripcion.objects.filter(usuario=user)
        if i.estado in (Inscripcion.Estado.PENDIENTE, Inscripcion.Estado.ACEPTADA)
    }
    filas = []
    for g in grupos:
        i = propias.get(g.pk)
        filas.append({
            "grupo": g,
            "solicitud": i,
            # Botón "Solicitar": sólo si el rol puede y no está ya dentro.
            "puede_solicitar": g.puede_solicitar(user),
            "es_miembro": bool(i and i.estado == Inscripcion.Estado.ACEPTADA),
            "solicitud_pendiente": bool(i and i.es_pendiente),
            "es_coordinador": g.es_coordinador(user),
        })
    return filas


@login_required
def lista(request):
    """Todos los roles ven los grupos; sólo docente/staff los publican."""
    grupos = Grupo.activos().select_related("coordinador")
    tipo = request.GET.get("tipo", "").strip().upper()
    if tipo in Grupo.Tipo.values:
        grupos = grupos.filter(tipo=tipo)
    return render(request, "investigacion/lista.html", {
        "filas": _filas_para(request.user, grupos),
        "puede_publicar": _puede_publicar(request.user),
        "puede_inscribirse": _puede_inscribirse(request.user),
        "es_coordinador": Grupo.objects.filter(coordinador=request.user).exists(),
        "tipo_activo": tipo,
        "tipos": Grupo.Tipo.choices,
    })


@login_required
@requiere_rol(*ROLES_PUBLICAN)
def crear(request):
    if request.method == "POST":
        form = GrupoForm(request.POST, creador=request.user)
        if form.is_valid():
            grupo = form.save(commit=False)
            grupo.creado_por = request.user
            grupo.save()
            AuditoriaLog.registrar(request, "GRUPO_INV_CREADO", grupo, grupo.nombre)
            messages.success(request, "Grupo publicado.")
            return redirect("investigacion:panel")
    else:
        form = GrupoForm(creador=request.user)
    return render(request, "investigacion/form.html",
                  {"form": form, "accion": "Crear"})


@login_required
@requiere_rol(*ROLES_PUBLICAN)
def editar(request, pk):
    grupo = get_object_or_404(Grupo, pk=pk)
    if not (grupo.creado_por_id == request.user.pk
            or grupo.es_coordinador(request.user)
            or _puede_publicar(request.user)):
        raise PermissionDenied("Solo el autor, el coordinador o staff puede editar.")
    if request.method == "POST":
        form = GrupoForm(request.POST, instance=grupo, creador=request.user)
        if form.is_valid():
            form.save()
            AuditoriaLog.registrar(request, "GRUPO_INV_EDITADO", grupo, grupo.nombre)
            messages.success(request, "Grupo actualizado.")
            return redirect("investigacion:panel")
    else:
        form = GrupoForm(instance=grupo, creador=request.user)
    return render(request, "investigacion/form.html",
                  {"form": form, "accion": "Guardar"})


@login_required
def toggle_activo(request, pk):
    """Activa/desactiva el grupo. No borra: conserva el historial."""
    grupo = get_object_or_404(Grupo, pk=pk)
    if not (grupo.es_coordinador(request.user) or _puede_publicar(request.user)):
        raise PermissionDenied("Solo el coordinador o staff puede activar/desactivar.")
    grupo.activo = not grupo.activo
    grupo.save(update_fields=["activo"])
    AuditoriaLog.registrar(
        request, "GRUPO_INV_" + ("ACTIVADO" if grupo.activo else "DESACTIVADO"),
        grupo, grupo.nombre)
    messages.success(request, "Grupo actualizado.")
    return redirect("investigacion:panel")


@login_required
def solicitar(request, pk):
    """Envía la solicitud: queda PENDIENTE hasta que responda el coordinador."""
    grupo = get_object_or_404(Grupo, pk=pk, activo=True)
    if not _puede_inscribirse(request.user):
        raise PermissionDenied("Solo docentes y estudiantes pueden inscribirse.")
    if not grupo.puede_solicitar(request.user):
        messages.warning(request, "No puedes solicitar inscripción en este grupo.")
        return redirect("investigacion:lista")
    form = SolicitudForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        inscripcion = form.save(commit=False)
        inscripcion.grupo = grupo
        inscripcion.usuario = request.user
        inscripcion.estado = Inscripcion.Estado.PENDIENTE
        inscripcion.save()
        AuditoriaLog.registrar(request, "INSCRIPCION_SOLICITADA", grupo,
                               f"{request.user} -> {grupo.nombre}")
        if grupo.coordinador_id:
            Notificacion.enviar(
                grupo.coordinador,
                "Nueva solicitud de inscripción a un grupo",
                f"{request.user} pidió unirse a {grupo.nombre}.",
                url="/investigacion/panel/",
            )
        messages.success(request, "Solicitud enviada. El coordinador la revisará.")
        return redirect("investigacion:lista")
    return render(request, "investigacion/solicitar.html",
                  {"form": form, "grupo": grupo})


@login_required
def cancelar(request, pk):
    """El usuario cancela su propia solicitud mientras siga pendiente."""
    inscripcion = get_object_or_404(Inscripcion, pk=pk, usuario=request.user)
    if not inscripcion.es_pendiente:
        messages.warning(request, "La solicitud ya fue respondida.")
        return redirect("investigacion:lista")
    inscripcion.estado = Inscripcion.Estado.CANCELADA
    inscripcion.respondida = timezone.now()
    inscripcion.save(update_fields=["estado", "respondida"])
    messages.success(request, "Solicitud cancelada.")
    return redirect("investigacion:lista")


@login_required
def panel(request):
    """Gestión del coordinador: sus grupos y las solicitudes pendientes."""
    mis_grupos = Grupo.objects.filter(coordinador=request.user)
    pendientes = (Inscripcion.objects
                  .filter(grupo__in=mis_grupos, estado=Inscripcion.Estado.PENDIENTE)
                  .select_related("usuario", "grupo"))
    return render(request, "investigacion/panel.html", {
        "mis_grupos": mis_grupos,
        "pendientes": pendientes,
        "puede_publicar": _puede_publicar(request.user),
    })


@login_required
def responder(request, pk):
    """El coordinador (o un ADMIN) acepta o rechaza una solicitud."""
    inscripcion = get_object_or_404(
        Inscripcion.objects.select_related("grupo", "usuario"), pk=pk)
    grupo = inscripcion.grupo
    if not grupo.es_coordinador(request.user):
        raise PermissionDenied("Solo el coordinador del grupo puede responder.")
    if not inscripcion.es_pendiente:
        messages.warning(request, "Esa solicitud ya fue respondida.")
        return redirect("investigacion:panel")
    accion = request.POST.get("accion")
    if accion == "aceptar":
        inscripcion.aceptar()
        AuditoriaLog.registrar(request, "INSCRIPCION_ACEPTADA", grupo,
                               f"{inscripcion.usuario} -> {grupo.nombre}")
        messages.success(request, "Solicitud aceptada.")
    elif accion == "rechazar":
        inscripcion.rechazar(motivo=request.POST.get("motivo", ""))
        AuditoriaLog.registrar(request, "INSCRIPCION_RECHAZADA", grupo,
                               f"{inscripcion.usuario} -> {grupo.nombre}")
        messages.success(request, "Solicitud rechazada.")
    return redirect("investigacion:panel")