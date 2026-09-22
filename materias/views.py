# =====================================================================
# Vistas de materias (RF-11 a RF-15)
# =====================================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from comun.mixins import MixinRol, requiere_rol, rol_usuario
from usuario.models import Usuario

from .forms import MallaCurricularForm, SolicitudMateriaForm
from .models import MallaCurricular, Materia, SolicitudMateria


class CatalogoView(ListView):
    """Catálogo público de materias publicadas (RF-15)."""

    template_name = "materias/catalogo.html"
    context_object_name = "materias"
    paginate_by = 15

    def get_queryset(self):
        q = self.request.GET.get("q", "").strip()
        filtro = Q(estado=Materia.Estado.PUBLICADA)
        if q:
            filtro &= Q(nombre__icontains=q) | Q(codigo__icontains=q)
        return Materia.objects.filter(filtro)


@login_required
def proponer_materia(request):
    """RF-11: docente propone crear una materia nueva."""
    if request.method == "POST":
        form = SolicitudMateriaForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                materia = Materia.objects.create(
                    codigo=form.cleaned_data["codigo_nuevo"],
                    nombre=form.cleaned_data["nombre"],
                    creditos=form.cleaned_data["creditos"],
                    cupo_maximo=form.cleaned_data["cupo_maximo"],
                    estado=Materia.Estado.PROPUESTA,
                )
                SolicitudMateria.objects.create(
                    materia=materia,
                    tipo=SolicitudMateria.Tipo.CREACION,
                    justificacion=form.cleaned_data["justificacion"],
                    propuesta={
                        "nombre": form.cleaned_data["nombre"],
                        "creditos": form.cleaned_data["creditos"],
                        "cupo_maximo": form.cleaned_data["cupo_maximo"],
                    },
                    solicitante=request.user,
                )
            messages.success(request, "Propuesta creada. Quedó en revisión del departamento.")
            return redirect("materias:panel")
    else:
        form = SolicitudMateriaForm()
    return render(request, "materias/proponer.html", {"form": form})


@login_required
def editar_materia(request, pk):
    """RF-12: docente solicita edición de una materia existente."""
    materia = get_object_or_404(Materia, pk=pk)
    if request.method == "POST":
        form = SolicitudMateriaForm(request.POST, materia=materia)
        if form.is_valid():
            with transaction.atomic():
                SolicitudMateria.objects.create(
                    materia=materia,
                    tipo=SolicitudMateria.Tipo.EDICION,
                    justificacion=form.cleaned_data["justificacion"],
                    propuesta=form.propuesta(),
                    solicitante=request.user,
                )
            messages.success(request, "Solicitud de edición enviada al departamento.")
            return redirect("materias:panel")
    else:
        form = SolicitudMateriaForm(materia=materia)
    return render(request, "materias/editar.html", {"form": form, "materia": materia})


class PanelMateriasView(MixinRol, ListView):
    """Panel del departamento: solicitudes pendientes de revisión (RF-13)."""

    roles_permitidos = ("DEPARTAMENTO",)
    template_name = "materias/panel.html"
    context_object_name = "solicitudes"
    paginate_by = 15

    def get_queryset(self):
        return SolicitudMateria.objects.select_related("materia", "solicitante")


@login_required
def revisar_solicitud(request, pk, decision):
    """RF-13: aprobar/rechazar la solicitud (RN-11)."""
    solicitud = get_object_or_404(SolicitudMateria, pk=pk)
    comentario = request.POST.get("comentario", "")
    if decision == "aprobar":
        solicitud.aprobar(request.user)
        messages.success(request, "Solicitud aprobada y materia publicada.")
    elif decision == "rechazar":
        solicitud.rechazar(request.user, comentario)
        messages.warning(request, "Solicitud rechazada.")
    return redirect("materias:panel")


# =====================================================================
# Maya curricular por estudiante (semáforo verde/amarillo/rojo)
# =====================================================================
SEMESTRES_PLAN = range(1, 11)  # plan de 10 semestres


def _puede_editar_malla(user):
    """Solo el administrativo (secretaría, departamento o admin) edita."""
    return rol_usuario(user) in ("SECRETARIA", "DEPARTAMENTO", "ADMIN")


def _es_docente_de(estudiante, user):
    """True si el docente dicta alguna materia inscrita por el estudiante.

    El docente solo consulta (nunca edita) y únicamente las mallas de los
    estudiantes que cursan materias bajo su responsabilidad.
    """
    if rol_usuario(user) != "DOCENTE":
        return False
    from cupos.models import Inscripcion

    return Inscripcion.objects.filter(
        estudiante=estudiante, oferta__materia__docentes=user
    ).exists()


def construir_malla(estudiante):
    """Construye las columnas (1-10) de la malla curricular del estudiante.

    Mezcla los registros guardados por el administrativo con las materias
    publicadas que aún no están ubicadas, para que el plan completo se vea.
    Cada celda expone ``color`` (verde/amarillo/rojo) y ``etiqueta``.
    """
    columnas = {numero: [] for numero in SEMESTRES_PLAN}
    filas = (MallaCurricular.objects
             .filter(estudiante=estudiante)
             .select_related("materia"))
    ids_registrados = set()

    for fila in filas:
        ids_registrados.add(fila.materia_id)
        semestre = fila.semestre if 1 <= fila.semestre <= 10 else 1
        columnas[semestre].append({
            "materia": fila.materia,
            "estado": fila.estado_efectivo,
            "color": fila.color,
            "etiqueta": fila.etiqueta_corta,
            "etiqueta_larga": fila.etiqueta_estado,
            "creditos": fila.materia.creditos,
            "observacion": fila.observacion,
            "en_malla": True,
        })

    # Materias publicadas aún sin ubicar: semestre por defecto de la materia.
    for materia in Materia.objects.filter(estado=Materia.Estado.PUBLICADA):
        if materia.pk in ids_registrados:
            continue
        semestre = materia.semestre if 1 <= materia.semestre <= 10 else 1
        provisional = MallaCurricular(estudiante=estudiante,
                                      materia=materia, semestre=semestre)
        columnas[semestre].append({
            "materia": materia,
            "estado": provisional.estado_efectivo,
            "color": provisional.color,
            "etiqueta": provisional.etiqueta_corta,
            "etiqueta_larga": provisional.etiqueta_estado,
            "creditos": materia.creditos,
            "observacion": "",
            "en_malla": False,
        })

    for items in columnas.values():
        items.sort(key=lambda item: item["materia"].codigo)
    return columnas


@login_required
def malla_estudiante(request, pk):
    """Consulta de la malla curricular (estudiante, docente o administrativo)."""
    estudiante = get_object_or_404(Usuario, pk=pk, rol="ESTUDIANTE")
    es_propio = estudiante.pk == request.user.pk
    es_admin = _puede_editar_malla(request.user)
    es_docente = _es_docente_de(estudiante, request.user)

    if not (es_propio or es_admin or es_docente):
        raise PermissionDenied("No tiene acceso a la malla de este estudiante.")

    columnas = construir_malla(estudiante)
    totales = {"verde": 0, "amarillo": 0, "rojo": 0}
    for items in columnas.values():
        for celda in items:
            totales[celda["color"]] += 1

    return render(request, "materias/malla.html", {
        "estudiante": estudiante,
        "columnas": columnas,
        "columnas_rejilla": [
            {"semestre": n, "items": columnas.get(n, [])}
            for n in SEMESTRES_PLAN
        ],
        "semestres": SEMESTRES_PLAN,
        "totales": totales,
        "puede_editar": es_admin,
        "es_propio": es_propio,
    })


@login_required
@requiere_rol("SECRETARIA", "DEPARTAMENTO", "ADMIN")
def editar_malla(request, pk):
    """El administrativo ubica una materia en un semestre y fija su estado."""
    if not _puede_editar_malla(request.user):
        raise PermissionDenied("Solo el administrativo puede modificar la malla.")

    estudiante = get_object_or_404(Usuario, pk=pk, rol="ESTUDIANTE")
    materia_id = request.POST.get("materia") or request.GET.get("materia")
    materia = get_object_or_404(Materia, pk=materia_id)
    fila, _ = MallaCurricular.objects.get_or_create(
        estudiante=estudiante, materia=materia,
        defaults={"semestre": materia.semestre},
    )

    if request.method == "POST":
        form = MallaCurricularForm(request.POST, instance=fila)
        if form.is_valid():
            with transaction.atomic():
                fila = form.save(commit=False)
                fila.actualizado_por = request.user
                fila.save()
                from comun.models import AuditoriaLog, Notificacion

                AuditoriaLog.registrar(
                    request, "EDITAR_MALLA_CURRICULAR", fila,
                    f"{estudiante} · {materia} · semestre {fila.semestre} · "
                    f"{fila.get_estado_display()}",
                )
                Notificacion.enviar(
                    estudiante,
                    "Malla curricular actualizada",
                    f"Su malla curricular fue actualizada: {materia} "
                    f"(semestre {fila.semestre}, {fila.get_estado_display()}).",
                    url=f"/materias/malla/{estudiante.pk}/",
                    correo=False,
                )
            messages.success(request, "Malla curricular actualizada.")
            return redirect("materias:malla", pk=estudiante.pk)
        messages.error(request, "Revise los datos del formulario.")
    else:
        form = MallaCurricularForm(instance=fila)

    return render(request, "materias/malla_editar.html", {
        "estudiante": estudiante,
        "materia": materia,
        "form": form,
        "fila": fila,
    })
