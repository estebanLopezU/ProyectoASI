# =====================================================================
# Vistas de reportes (RF-43 a RF-50)
# =====================================================================
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comun.mixins import requiere_rol
from comun.models import AuditoriaLog, Notificacion
from .models import PlantillaReporte, ProgramacionReporte, ReporteGenerado
from .servicios import exportar, generar_filas

EXTENSIONES = {"CSV": "csv", "XLSX": "xlsx", "PDF": "pdf"}


@requiere_rol("SECRETARIA", "DEPARTAMENTO", "DOCENTE")
def panel(request):
    """RF-44: catálogo de reportes disponibles y últimos generados."""
    return render(request, "reportes/panel.html", {
        "plantillas": PlantillaReporte.objects.filter(activa=True),
        "recientes": ReporteGenerado.objects.select_related("plantilla")[:10],
        "tipos": PlantillaReporte.Tipo.choices,
    })


@requiere_rol("SECRETARIA", "DEPARTAMENTO", "DOCENTE")
def generar(request, pk):
    """RF-45/RF-46: genera y deja disponible la descarga del reporte."""
    plantilla = get_object_or_404(PlantillaReporte, pk=pk)
    formato = request.POST.get("formato") or request.GET.get("formato") or "CSV"
    parametros = dict(plantilla.filtros or {})
    for clave in ("periodo", "desde", "hasta", "estado", "min_porcentaje"):
        valor = request.POST.get(clave)
        if valor:
            parametros[clave] = valor
    reporte = ReporteGenerado.objects.create(
        plantilla=plantilla, solicitado_por=request.user,
        parametros=parametros, formato=formato,
    )
    try:
        filas = generar_filas(plantilla.tipo, parametros)
        reporte.marcar_listo(max(len(filas) - 1, 0),
                             contenido=exportar(filas, "CSV").decode("utf-8"))
        AuditoriaLog.registrar(request, "GENERAR_REPORTE", reporte,
                               f"{plantilla.nombre} ({formato})")
        messages.success(request, f"Reporte generado: {reporte.total_registros} registros.")
    except Exception as error:  # protección de la vista ante datos inconsistentes
        reporte.estado = ReporteGenerado.Estado.ERROR
        reporte.mensaje_error = str(error)[:300]
        reporte.save()
        messages.error(request, f"No fue posible generar el reporte: {error}")
    return redirect("reportes:detalle", reporte.pk)


@requiere_rol("SECRETARIA", "DEPARTAMENTO", "DOCENTE")
def detalle(request, pk):
    """RF-46: vista previa y descarga del reporte generado."""
    reporte = get_object_or_404(ReporteGenerado, pk=pk)
    filas = []
    if reporte.estado == ReporteGenerado.Estado.LISTO:
        try:
            filas = generar_filas(reporte.plantilla.tipo, reporte.parametros)
        except ValueError:
            filas = []
    return render(request, "reportes/detalle.html",
                  {"reporte": reporte, "filas": filas[:200]})


@requiere_rol("SECRETARIA", "DEPARTAMENTO", "DOCENTE")
def descargar(request, pk):
    """RF-46: descarga en CSV/Excel/PDF según el parámetro `formato`."""
    reporte = get_object_or_404(ReporteGenerado, pk=pk)
    formato = request.GET.get("formato", reporte.formato)
    filas = generar_filas(reporte.plantilla.tipo, reporte.parametros)
    contenido = exportar(filas, formato)
    extension = EXTENSIONES.get(formato, "csv")
    nombre = f"{reporte.plantilla.tipo.lower()}-{timezone.localdate():%Y%m%d}.{extension}"
    respuesta = HttpResponse(contenido, content_type="application/octet-stream")
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    AuditoriaLog.registrar(request, "DESCARGAR_REPORTE", reporte, f"{nombre} ({formato})")
    return respuesta


@requiere_rol("DEPARTAMENTO", "SECRETARIA", "ADMIN")
def programaciones(request):
    """RF-48: programación de envíos periódicos."""
    if request.method == "POST":
        plantilla = get_object_or_404(PlantillaReporte, pk=request.POST.get("plantilla"))
        programacion, creada = ProgramacionReporte.objects.get_or_create(
            plantilla=plantilla,
            defaults={"frecuencia": request.POST.get("frecuencia", "SEMANAL"),
                      "formato": request.POST.get("formato", "CSV")},
        )
        if not creada:
            programacion.frecuencia = request.POST.get("frecuencia", programacion.frecuencia)
            programacion.formato = request.POST.get("formato", programacion.formato)
        programacion.calcular_proxima()
        messages.success(request, "Programación registrada.")
        return redirect("reportes:programaciones")
    return render(request, "reportes/programaciones.html", {
        "programaciones": ProgramacionReporte.objects.select_related("plantilla"),
        "plantillas": PlantillaReporte.objects.filter(activa=True),
        "formato_choices": ReporteGenerado.Formato.choices,
        "frecuencias": ProgramacionReporte.Frecuencia.choices,
    })


@requiere_rol("DEPARTAMENTO", "SECRETARIA", "ADMIN")
def ejecutar_programaciones(request):
    """RF-48: ejecuta las programaciones vencidas y notifica a los destinatarios."""
    ejecutadas = 0
    for programacion in ProgramacionReporte.objects.filter(activa=True):
        if not programacion.esta_vencida():
            continue
        filas = generar_filas(programacion.plantilla.tipo, programacion.plantilla.filtros)
        reporte = ReporteGenerado.objects.create(
            plantilla=programacion.plantilla, solicitado_por=request.user,
            parametros=programacion.plantilla.filtros, formato=programacion.formato,
        )
        reporte.marcar_listo(max(len(filas) - 1, 0),
                             contenido=exportar(filas, "CSV").decode("utf-8"))
        for destinatario in programacion.destinatarios.all():
            Notificacion.enviar(
                destinatario, f"Reporte programado: {programacion.plantilla.nombre}",
                f"Se generó el reporte {programacion.plantilla.nombre} "
                f"({reporte.total_registros} registros).",
                url=f"/reportes/{reporte.pk}/",
            )
        programacion.ultima_ejecucion = timezone.now()
        programacion.calcular_proxima()
        ejecutadas += 1
    messages.success(request, f"Programaciones ejecutadas: {ejecutadas}.")
    return redirect("reportes:programaciones")

