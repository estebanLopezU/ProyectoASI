# =====================================================================
# Vistas de mensajería (RF-16 a RF-20)
# =====================================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from comun.mixins import rol_usuario
from comun.models import Notificacion
from .forms import MensajeForm, NuevoHiloForm
from .models import Hilo, Mensaje


class BandejaView(ListView):
    """Bandeja de entrada del usuario autenticado."""

    template_name = "mensajes/bandeja.html"
    context_object_name = "hilos"
    paginate_by = 15

    def get_queryset(self):
        usuario = self.request.user
        return Hilo.objects.filter(
            Q(estudiante=usuario) | Q(docente=usuario) | Q(intervenido_por=usuario)
        ).select_related("estudiante", "docente", "materia")


@login_required
def nuevo_hilo(request):
    """RF-16: el estudiante inicia un hilo con un docente de su inscripción."""
    if rol_usuario(request.user) != "ESTUDIANTE":
        messages.error(request, "La creación de hilos es para estudiantes.")
        return redirect("mensajes:bandeja")
    if request.method == "POST":
        form = NuevoHiloForm(request.POST, estudiante=request.user)
        if form.is_valid():
            hilo = form.save()
            Mensaje.objects.create(
                hilo=hilo, autor=request.user, contenido=form.cleaned_data["contenido"]
            )
            Notificacion.enviar(
                hilo.docente,
                "Nuevo mensaje de estudiante",
                f"{request.user}: {hilo.asunto}",
                url=hilo.get_absolute_url(),
            )
            messages.success(request, "Mensaje enviado.")
            return redirect("mensajes:hilo", hilo.pk)
    else:
        form = NuevoHiloForm(estudiante=request.user)
    return render(request, "mensajes/nuevo.html", {"form": form})


@login_required
def ver_hilo(request, pk):
    """Ver hilo, marcar lectura y responder (RF-16/RF-17/RF-18)."""
    hilo = get_object_or_404(Hilo, pk=pk)
    usuario = request.user
    if not hilo.participante(usuario):
        messages.error(request, "No participa en este hilo.")
        return redirect("mensajes:bandeja")
    # Marca como leídos los mensajes del otro participante (RF-18)
    hilo.mensajes.exclude(autor=usuario).filter(leido=False).update(leido=True)
    if request.method == "POST":
        form = MensajeForm(request.POST)
        if form.is_valid():
            Mensaje.objects.create(
                hilo=hilo, autor=usuario, contenido=form.cleaned_data["contenido"]
            )
            destinatario = hilo.estudiante if usuario.pk == hilo.docente_id else hilo.docente
            Notificacion.enviar(
                destinatario,
                f"Respuesta: {hilo.asunto}",
                f"{usuario.get_full_name() or usuario.username} respondió al hilo.",
                url=hilo.get_absolute_url(),
            )
            messages.success(request, "Respuesta enviada.")
            return redirect("mensajes:hilo", hilo.pk)
    else:
        form = MensajeForm()
    return render(request, "mensajes/hilo.html", {"hilo": hilo, "form": form})


@login_required
def intervenir_hilo(request, pk):
    """RF-20: secretaría interviene un hilo escalado."""
    hilo = get_object_or_404(Hilo, pk=pk)
    if rol_usuario(request.user) not in ("SECRETARIA", "ADMIN"):
        messages.error(request, "Solo secretaría puede intervenir hilos.")
        return redirect("mensajes:bandeja")
    hilo.intervenido_por = request.user
    hilo.tipo = Hilo.Tipo.ADMINISTRATIVO
    hilo.save(update_fields=["intervenido_por", "tipo"])
    Notificacion.enviar(
        hilo.estudiante,
        "Secretaría intervino su conversación",
        f"{request.user.get_full_name() or request.user.username} participa ahora "
        f"en el hilo «{hilo.asunto}».",
        url=hilo.get_absolute_url(),
        nivel=Notificacion.Nivel.ADVERTENCIA,
    )
    messages.success(request, "Intervención registrada; ahora participa en el hilo.")
    return redirect("mensajes:hilo", hilo.pk)
