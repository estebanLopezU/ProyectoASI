# =====================================================================
# Vistas de quejas: radicación, seguimiento, escalamiento y cierre
# RF-35 a RF-42 · RN-09 a RN-12
# =====================================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from comun.mixins import es_staff, requiere_rol
from comun.models import AuditoriaLog
from .forms import CierreForm, EscalamientoMasivoForm, GestionQuejaForm, QuejaForm
from .models import CategoriaQueja, Queja, Seguimiento


@login_required
def mis_quejas(request):
    """RF-41: el usuario consulta el estado de sus casos."""
    quejas = Queja.objects.filter(radicada_por=request.user)
    return render(request, "quejas/mis_quejas.html", {"quejas": quejas})


@login_required
def radicar(request):
    """RF-35/RF-36: radicación con categoría y opción anónima (RN-09)."""
    if request.method == "POST":
        form = QuejaForm(request.POST, request.FILES)
        if form.is_valid():
            queja = form.save(commit=False)
            queja.radicada_por = request.user
            queja.save()
            AuditoriaLog.registrar(request, "RADICAR_QUEJA", queja,
                                   f"Categoría: {queja.categoria}")
            if queja.categoria.solucion_rapida:
                messages.info(request, "Sugerencia inmediata: "
                              + queja.categoria.solucion_rapida)
            messages.success(request, f"Queja radicada con consecutivo {queja.consecutivo}.")
            return redirect("quejas:detalle", queja.pk)
    else:
        form = QuejaForm()
    return render(request, "quejas/radicar.html",
                  {"form": form, "categorias": CategoriaQueja.objects.filter(activa=True)})


@login_required
def detalle(request, pk):
    """Trazabilidad del caso (RF-40); RN-09 oculta al denunciante anónimo."""
    queja = get_object_or_404(Queja, pk=pk)
    propio = queja.radicada_por_id == request.user.pk
    if not propio and not es_staff(request.user):
        messages.error(request, "No tiene acceso a este caso.")
        return redirect("quejas:mis_quejas")
    return render(request, "quejas/detalle.html", {
        "queja": queja, "seguimientos": queja.seguimientos.select_related("autor"),
        "propio": propio, "cierre_form": CierreForm(),
    })


@requiere_rol("SECRETARIA", "DEPARTAMENTO", "DOCENTE")
def panel_gestion(request):
    """RF-37/RF-41: panel de gestión con métricas del proceso."""
    quejas = Queja.objects.select_related("categoria", "gestor", "radicada_por")
    estado = request.GET.get("estado")
    if estado:
        quejas = quejas.filter(estado=estado)
    if request.user.rol == "DOCENTE":
        quejas = quejas.filter(Q(gestor=request.user) | Q(gestor__isnull=True))
    metricas = {
        "total": Queja.objects.count(),
        "abiertas": Queja.objects.filter(estado=Queja.Estado.ABIERTO).count(),
        "en_proceso": Queja.objects.filter(estado=Queja.Estado.EN_PROCESO).count(),
        "escaladas": Queja.objects.filter(estado=Queja.Estado.ESCALADO).count(),
        "resueltas": Queja.objects.filter(
            estado__in=(Queja.Estado.RESUELTO, Queja.Estado.CERRADO)).count(),
        "por_categoria": Queja.objects.values("categoria__nombre").annotate(
            total=Count("id")).order_by("-total"),
    }
    return render(request, "quejas/panel.html", {"quejas": quejas, "metricas": metricas})


@requiere_rol("SECRETARIA", "DEPARTAMENTO", "DOCENTE")
def gestionar(request, pk):
    """RF-37 a RF-39: acciones de gestión sobre el caso."""
    queja = get_object_or_404(Queja, pk=pk)
    if request.method == "POST":
        form = GestionQuejaForm(request.POST)
        if form.is_valid():
            accion = form.cleaned_data["accion"]
            detalle = form.cleaned_data["detalle"]
            if accion == "ASIGNAR":
                queja.asignar(form.cleaned_data["gestor"] or request.user, detalle)
            elif accion == "RESOLVER":
                queja.resolver(request.user, detalle or queja.categoria.solucion_rapida)
            elif accion == "SOLUCION_RAPIDA":
                if not queja.aplicar_solucion_rapida(request.user, detalle):
                    messages.warning(request, "La categoría no tiene solución rápida (RN-11).")
                    return redirect("quejas:gestionar", queja.pk)
            elif accion == "ESCALAR":
                queja.escalar(detalle)
                queja.seguimientos.create(autor=request.user,
                                          tipo=Seguimiento.Tipo.ESCALAMIENTO,
                                          detalle=detalle or "Escalamiento manual.")
            else:
                queja.seguimiento(request.user, detalle or "Avance registrado.")
            AuditoriaLog.registrar(request, f"QUEJA_{accion}", queja, detalle)
            messages.success(request, "Gestión registrada.")
            return redirect("quejas:detalle", queja.pk)
    else:
        form = GestionQuejaForm()
    return render(request, "quejas/gestionar.html", {"form": form, "queja": queja})


@login_required
def confirmar(request, pk):
    """RF-42/RN-12: el usuario confirma la solución y califica."""
    queja = get_object_or_404(Queja, pk=pk, radicada_por=request.user)
    if request.method == "POST":
        form = CierreForm(request.POST)
        if form.is_valid():
            queja.confirmar_cierre(int(form.cleaned_data["satisfaccion"]))
            messages.success(request, "Gracias por confirmar el cierre del caso.")
            return redirect("quejas:mis_quejas")
    return render(request, "quejas/confirmar.html", {"queja": queja, "form": CierreForm()})


@login_required
def reabrir(request, pk):
    """RN-12: reapertura cuando la solución no fue efectiva."""
    queja = get_object_or_404(Queja, pk=pk, radicada_por=request.user)
    if request.method == "POST":
        queja.reabrir(request.POST.get("comentario", ""))
        messages.warning(request, "Caso reabierto; el gestor fue notificado.")
    return redirect("quejas:detalle", queja.pk)


@requiere_rol("SECRETARIA", "DEPARTAMENTO")
def casos_vencidos(request):
    """RF-38/RN-10: escala los casos sin gestión en el plazo configurado."""
    vencidos = [q for q in Queja.objects.exclude(
        estado__in=(Queja.Estado.RESUELTO, Queja.Estado.CERRADO,
                    Queja.Estado.ESCALADO)) if q.requiere_escalamiento()]
    if request.method == "POST":
        form = EscalamientoMasivoForm(request.POST)
        if form.is_valid():
            escalados = 0
            for queja in form.cleaned_data["casos"]:
                escalados += int(queja.escalar("Escalamiento masivo por vencimiento (RN-10)."))
            messages.success(request, f"Casos escalados: {escalados}.")
            return redirect("quejas:vencidos")
    else:
        form = EscalamientoMasivoForm()
    return render(request, "quejas/vencidos.html", {
        "vencidos": vencidos, "form": form,
        "dias": request.sgdic_config["dias_escalamiento"],
    })

