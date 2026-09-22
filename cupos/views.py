# =====================================================================
# Vistas de cupos (RF-05 a RF-10) y preinscripción de asignaturas
# (RN-13, RN-14)
# =====================================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView

from comun.mixins import MixinRol, MixinStaff, rol_usuario
from .models import (Inscripcion, OfertaCupo, PreferenciaPreinscripcion,
                     Preinscripcion, SolicitudCupo)


class OfertasView(ListView):
    """RF-05: catálogo de ofertas con disponibilidad en tiempo real."""

    template_name = "cupos/ofertas.html"
    context_object_name = "ofertas"
    paginate_by = 12

    def get_queryset(self):
        qs = OfertaCupo.objects.filter(activa=True).select_related("materia")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(materia__nombre__icontains=q) | Q(materia__codigo__icontains=q))
        return qs


@login_required
def solicitar_cupo(request, oferta_id):
    """RF-05: el estudiante solicita un cupo y el sistema valida (RF-06)."""
    if request.method != "POST":
        return redirect("cupos:ofertas")
    if rol_usuario(request.user) != "ESTUDIANTE":
        messages.error(request, "Solo los estudiantes pueden solicitar cupos.")
        return redirect("cupos:ofertas")
    oferta = get_object_or_404(OfertaCupo, pk=oferta_id, activa=True)
    solicitud, creada = SolicitudCupo.objects.get_or_create(
        oferta=oferta, estudiante=request.user
    )
    if not creada:
        messages.info(request, "Ya tiene una solicitud para esta oferta.")
        return redirect("cupos:mis_solicitudes")
    solicitud.procesar()
    messages.success(
        request, f"Solicitud procesada: {solicitud.get_estado_display()}."
    )
    return redirect("cupos:mis_solicitudes")


class MisSolicitudesView(ListView):
    """RF-08: el estudiante consulta el resultado de sus solicitudes."""

    template_name = "cupos/mis_solicitudes.html"
    context_object_name = "solicitudes"

    def get_queryset(self):
        return (
            SolicitudCupo.objects.filter(estudiante=self.request.user)
            .select_related("oferta", "oferta__materia")
        )


@login_required
def confirmar_cupo(request, inscripcion_id):
    """RF-09: el estudiante confirma la inscripción dentro del plazo."""
    inscripcion = get_object_or_404(
        Inscripcion, pk=inscripcion_id, estudiante=request.user, estado=Inscripcion.Estado.ACTIVA
    )
    inscripcion.confirmada = timezone.now()
    inscripcion.save(update_fields=["confirmada"])
    messages.success(request, "Cupo confirmado.")
    return redirect("cupos:inscripciones")


class MisInscripcionesView(ListView):
    template_name = "cupos/inscripciones.html"
    context_object_name = "inscripciones"

    def get_queryset(self):
        return (
            Inscripcion.objects.filter(estudiante=self.request.user)
            .select_related("oferta", "oferta__materia")
        )


class ListaEsperaView(MixinStaff, ListView):
    """RF-10: secretaría ve y gestiona la lista de espera por materia."""

    template_name = "cupos/lista_espera.html"
    context_object_name = "solicitudes"

    def get_queryset(self):
        qs = SolicitudCupo.objects.select_related("oferta__materia", "estudiante")
        oferta_id = self.request.GET.get("oferta")
        if oferta_id:
            qs = qs.filter(oferta_id=oferta_id)
        return qs.order_by("oferta_id", "-prioridad", "creada")


@login_required
def procesar_pendientes(request):
    """RF-07: procesa solicitudes pendientes respetando la prioridad."""
    if rol_usuario(request.user) not in ("SECRETARIA", "DEPARTAMENTO", "ADMIN"):
        messages.error(request, "No tiene permisos para esta operación.")
        return redirect("dashboard")
    pendientes = SolicitudCupo.objects.filter(estado=SolicitudCupo.Estado.PENDIENTE)
    total = 0
    for solicitud in pendientes.order_by("-prioridad", "creada"):
        solicitud.procesar()
        total += 1
    messages.success(request, f"{total} solicitudes procesadas.")
    return redirect("cupos:lista_espera")


# =====================================================================
# Preinscripción de asignaturas (RN-13, RN-14)
# =====================================================================
class MateriaDisponibleService:
    """Catálogo de materias que el estudiante puede preinscribir (RN-13)."""

    def __init__(self, estudiante, periodo):
        self.estudiante = estudiante
        self.periodo = periodo

    def catalogo(self, excluir=()):
        """Materias publicadas con docentes activos y su demanda agregada."""
        from django.db.models import Count

        from materias.models import Materia

        from .preinscripcion import demanda_historica, docentes_activos

        materias = (Materia.objects
                    .filter(estado=Materia.Estado.PUBLICADA)
                    .exclude(pk__in=excluir)
                    .prefetch_related("docentes"))

        demanda_por_materia = {
            fila["materia_id"]: fila["total"]
            for fila in (Preinscripcion.objects
                         .filter(periodo_objetivo=self.periodo)
                         .values("materia_id")
                         .annotate(total=Count("id")))
        }

        catalogo = []
        for materia in materias:
            docentes = docentes_activos(materia)
            catalogo.append({
                "materia": materia,
                "docentes": docentes,
                "docentes_detalle": list(materia.docentes.all()),
                "demanda": demanda_por_materia.get(materia.pk, 0),
                "historico": round(demanda_historica(materia, self.periodo), 1),
                "creditos": materia.creditos,
                "requiere_docente": docentes == 0,
            })
        return catalogo


class PreinscripcionView(MixinRol, ListView):
    """RN-13: el estudiante arma su preinscripción del próximo periodo.

    Muestra las materias preinscritas con su probabilidad estimada, los
    docentes activos, las franjas compatibles y el catálogo disponible.
    """

    template_name = "cupos/preinscripcion.html"
    context_object_name = "preinscripciones"
    roles_permitidos = ("ESTUDIANTE",)

    def get_queryset(self):
        from .preinscripcion import calcular_probabilidades, periodo_objetivo_actual

        self.periodo = periodo_objetivo_actual()
        # Recalcula la demanda agregada antes de listar
        calcular_probabilidades(self.periodo, estudiante=self.request.user)
        return (Preinscripcion.objects
                .filter(estudiante=self.request.user, periodo_objetivo=self.periodo)
                .select_related("materia")
                .prefetch_related("materia__docentes"))

    def get_context_data(self, **kwargs):
        from .preinscripcion import (alertas_prerrequisitos, construir_horario,
                                     franjas_estudiante, periodo_objetivo_actual,
                                     resumen_preinscripcion)

        contexto = super().get_context_data(**kwargs)
        periodo = getattr(self, "periodo", periodo_objetivo_actual())
        contexto["periodo"] = periodo
        contexto["resumen"] = resumen_preinscripcion(self.request.user, periodo)
        contexto["alertas"] = alertas_prerrequisitos(self.request.user, periodo)
        contexto["preferencias"] = franjas_estudiante(self.request.user, periodo)

        # Franjas ya asignadas a las materias preinscritas (por prioridad)
        reservadas = set()
        for preinscripcion in contexto["preinscripciones"].order_by("prioridad"):
            if preinscripcion.franja_sugerida:
                for slot in construir_horario(self.request.user):
                    etiqueta = (f"{slot['nombre_dia']} "
                                f"{slot['inicio']:%H:%M}-{slot['fin']:%H:%M}")
                    if etiqueta == preinscripcion.franja_sugerida:
                        reservadas.add(slot["clave"])
        contexto["horario"] = construir_horario(self.request.user, reservadas=reservadas)
        contexto["dias"] = PreferenciaPreinscripcion.DIAS
        contexto["franjas"] = PreferenciaPreinscripcion.Franja.choices
        contexto["minimo"] = Preinscripcion.MINIMO_MATERIAS
        ya = set(contexto["preinscripciones"].values_list("materia_id", flat=True))
        contexto["disponibles"] = MateriaDisponibleService(
            self.request.user, periodo).catalogo(excluir=ya)
        return contexto


def _renumerar(estudiante, periodo):
    """Mantiene la secuencia de prioridades 1..N sin huecos (RN-13)."""
    lista = Preinscripcion.objects.filter(
        estudiante=estudiante, periodo_objetivo=periodo).order_by("prioridad", "creada")
    for indice, preinscripcion in enumerate(lista, start=1):
        if preinscripcion.prioridad != indice:
            Preinscripcion.objects.filter(pk=preinscripcion.pk).update(prioridad=indice)


@login_required
def preinscribir_materia(request, materia_id):
    """RN-13: agrega una materia a la preinscripción con su prioridad."""
    if request.method != "POST":
        return redirect("cupos:preinscripcion")
    if rol_usuario(request.user) != "ESTUDIANTE":
        messages.error(request, "Solo los estudiantes pueden preinscribirse.")
        return redirect("cupos:preinscripcion")

    from materias.models import Materia

    from .preinscripcion import calcular_probabilidades, periodo_objetivo_actual

    periodo = periodo_objetivo_actual()
    materia = get_object_or_404(Materia, pk=materia_id, estado=Materia.Estado.PUBLICADA)

    if Preinscripcion.objects.filter(estudiante=request.user, materia=materia,
                                     periodo_objetivo=periodo).exists():
        messages.info(request, f"{materia.nombre} ya está en su preinscripción.")
        return redirect("cupos:preinscripcion")

    ultima = (Preinscripcion.objects
              .filter(estudiante=request.user, periodo_objetivo=periodo)
              .order_by("-prioridad").first())
    prioridad = (ultima.prioridad + 1) if ultima else 1

    preinscripcion = Preinscripcion.objects.create(
        estudiante=request.user, materia=materia, periodo_objetivo=periodo,
        prioridad=prioridad, estado=Preinscripcion.Estado.ENVIADA,
    )
    calcular_probabilidades(periodo, estudiante=request.user)
    preinscripcion.refresh_from_db()
    messages.success(
        request,
        f"{materia.nombre} agregada en la posición {prioridad} "
        f"(probabilidad estimada {preinscripcion.porcentaje}%).",
    )
    return redirect("cupos:preinscripcion")


@login_required
def quitar_preinscripcion(request, preinscripcion_id):
    """RN-13: retira una materia y reordena las prioridades restantes."""
    if request.method != "POST":
        return redirect("cupos:preinscripcion")
    preinscripcion = get_object_or_404(Preinscripcion, pk=preinscripcion_id,
                                       estudiante=request.user)
    periodo = preinscripcion.periodo_objetivo
    nombre = preinscripcion.materia.nombre
    preinscripcion.delete()
    _renumerar(request.user, periodo)
    from .preinscripcion import calcular_probabilidades
    calcular_probabilidades(periodo, estudiante=request.user)
    messages.success(request, f"{nombre} retirada de la preinscripción.")
    return redirect("cupos:preinscripcion")


@login_required
def mover_prioridad(request, preinscripcion_id, direccion):
    """RN-13: sube o baja una materia en el orden de preferencia."""
    if request.method != "POST":
        return redirect("cupos:preinscripcion")
    preinscripcion = get_object_or_404(Preinscripcion, pk=preinscripcion_id,
                                       estudiante=request.user)
    lista = list(Preinscripcion.objects.filter(
        estudiante=request.user, periodo_objetivo=preinscripcion.periodo_objetivo
    ).order_by("prioridad", "creada"))
    indice = next((i for i, p in enumerate(lista) if p.pk == preinscripcion.pk), None)
    if indice is None:
        return redirect("cupos:preinscripcion")
    destino = indice - 1 if direccion == "subir" else indice + 1
    if 0 <= destino < len(lista):
        lista[indice], lista[destino] = lista[destino], lista[indice]
        for posicion, item in enumerate(lista, start=1):
            Preinscripcion.objects.filter(pk=item.pk).update(prioridad=posicion)
        from .preinscripcion import calcular_probabilidades
        calcular_probabilidades(preinscripcion.periodo_objetivo, estudiante=request.user)
        messages.success(request, "Orden de preferencia actualizado.")
    return redirect("cupos:preinscripcion")


@login_required
def guardar_preferencias(request):
    """RN-14: guarda las franjas horarias preferidas del estudiante."""
    if request.method != "POST":
        return redirect("cupos:preinscripcion")
    from .preinscripcion import calcular_probabilidades, periodo_objetivo_actual

    periodo = periodo_objetivo_actual()
    seleccionadas = request.POST.getlist("franja")
    dias = [int(d) for d in request.POST.getlist("dia") if d.isdigit()]

    PreferenciaPreinscripcion.objects.filter(
        estudiante=request.user, periodo_objetivo=periodo).delete()
    creadas = 0
    for valor in seleccionadas:
        try:
            dia, franja = valor.split(":")
            dia = int(dia)
        except (ValueError, AttributeError):
            continue
        if dias and dia not in dias:
            continue
        _, creada = PreferenciaPreinscripcion.objects.get_or_create(
            estudiante=request.user, periodo_objetivo=periodo, dia=dia, franja=franja)
        creadas += 1 if creada else 0
    calcular_probabilidades(periodo, estudiante=request.user)
    messages.success(request, f"{creadas} franjas horarias guardadas.")
    return redirect("cupos:preinscripcion")


@login_required
def enviar_preinscripcion(request):
    """RN-13: valida el mínimo de materias y notifica a secretaría."""
    if request.method != "POST":
        return redirect("cupos:preinscripcion")
    from comun.models import Notificacion

    from .preinscripcion import (alertas_prerrequisitos, calcular_probabilidades,
                                 periodo_objetivo_actual, resumen_preinscripcion)

    periodo = periodo_objetivo_actual()
    calcular_probabilidades(periodo, estudiante=request.user)
    resumen = resumen_preinscripcion(request.user, periodo)

    if not resumen["cumple_minimo"]:
        messages.error(
            request,
            f"Debe preinscribir al menos {resumen['minimo']} materias "
            f"(lleva {resumen['total']}).",
        )
        return redirect("cupos:preinscripcion")

    if not PreferenciaPreinscripcion.objects.filter(
            estudiante=request.user, periodo_objetivo=periodo).exists():
        messages.warning(request, "Declare al menos una franja horaria preferida (RN-14).")
        return redirect("cupos:preinscripcion")

    Preinscripcion.objects.filter(
        estudiante=request.user, periodo_objetivo=periodo
    ).update(estado=Preinscripcion.Estado.ENVIADA)

    from django.contrib.auth import get_user_model
    Usuario = get_user_model()
    for gestor in Usuario.objects.filter(rol__in=("SECRETARIA", "DEPARTAMENTO")):
        Notificacion.enviar(
            gestor,
            "Nueva preinscripción de asignaturas",
            f"{request.user.get_full_name() or request.user.username} preinscribió "
            f"{resumen['total']} materias para {periodo} ({resumen['creditos']} créditos).",
            url="/cupos/lista-espera/",
        )

    alertas = alertas_prerrequisitos(request.user, periodo)
    if alertas:
        messages.warning(
            request,
            f"Preinscripción enviada con {len(alertas)} alerta(s) de prerrequisitos "
            "pendientes (RN-01); podrían rechazarse al procesarse.",
        )
    else:
        messages.success(
            request,
            f"Preinscripción de {resumen['total']} materias enviada para {periodo}.",
        )
    return redirect("cupos:preinscripcion")
