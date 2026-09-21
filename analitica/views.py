# =====================================================================
# Vistas de analítica (RF-51 a RF-56)
# =====================================================================
from django.contrib import messages
from django.db.models import Avg, Count
from django.shortcuts import redirect, render

from comun.mixins import requiere_rol
from .models import (EPSILON, FACTOR_IMPACTO, FACTOR_URGENCIA,
                     NecesidadDetectada, PrediccionDemanda)
from .servicios import (actualizar_demanda_real, ejecutar_deteccion, predecir_todas)


@requiere_rol("DEPARTAMENTO", "SECRETARIA", "ADMIN")
def tablero(request):
    """RF-53/RF-56: priorización visual de necesidades por score."""
    necesidades = NecesidadDetectada.objects.all()
    if request.GET.get("periodo"):
        necesidades = necesidades.filter(periodo=request.GET["periodo"])
    agrupadas = {
        "CRITICA": [n for n in necesidades if n.nivel_prioridad == "CRITICA"],
        "ALTA": [n for n in necesidades if n.nivel_prioridad == "ALTA"],
        "MEDIA": [n for n in necesidades if n.nivel_prioridad == "MEDIA"],
        "BAJA": [n for n in necesidades if n.nivel_prioridad == "BAJA"],
    }
    resumen_origen = necesidades.values("origen").annotate(
        total=Count("id"), score_promedio=Avg("score")).order_by("-total")
    return render(request, "analitica/tablero.html", {
        "agrupadas": agrupadas, "necesidades": necesidades,
        "resumen_origen": resumen_origen,
        "total": necesidades.count(),
        "epsilon": EPSILON,
        "periodos": NecesidadDetectada.objects.values_list(
            "periodo", flat=True).distinct(),
    })


@requiere_rol("DEPARTAMENTO", "SECRETARIA", "ADMIN")
def detectar(request):
    """RF-51/RF-52: ejecuta el motor de detección de necesidades."""
    if request.method == "POST":
        resultado = ejecutar_deteccion(request.POST.get("periodo") or None)
        messages.success(
            request,
            f"Detección completada para {resultado['periodo']}: "
            f"{resultado['total']} necesidades identificadas.",
        )
        return redirect("analitica:tablero")
    return render(request, "analitica/detectar.html", {
        "epsilon": EPSILON, "factores_impacto": FACTOR_IMPACTO,
        "factores_urgencia": FACTOR_URGENCIA,
    })


@requiere_rol("DEPARTAMENTO", "SECRETARIA", "ADMIN")
def simulador(request):
    """RF-56: simulador interactivo del score (I×U)/(E+ε)."""
    datos = {"impacto": "ALTO", "urgencia": "DOCENTE", "esfuerzo": 8}
    if request.GET:
        datos = {
            "impacto": request.GET.get("impacto", datos["impacto"]),
            "urgencia": request.GET.get("urgencia", datos["urgencia"]),
            "esfuerzo": float(request.GET.get("esfuerzo") or datos["esfuerzo"]),
        }
    simulado = NecesidadDetectada(titulo="Simulación", **datos)
    score = simulado.calcular_score()
    return render(request, "analitica/simulador.html", {
        "datos": datos, "score": score, "nivel": simulado.nivel_prioridad,
        "recomendacion": simulado.recomendar(), "epsilon": EPSILON,
        "factores_impacto": FACTOR_IMPACTO, "factores_urgencia": FACTOR_URGENCIA,
    })


@requiere_rol("DEPARTAMENTO", "SECRETARIA", "ADMIN")
def predicciones(request):
    """RF-54/RF-55: demanda proyectada y error contra la demanda real."""
    if request.method == "POST":
        periodo = request.POST.get("periodo") or None
        generadas = predecir_todas(periodo)
        messages.success(request, f"Predicciones generadas: {len(generadas)}.")
        return redirect("analitica:predicciones")
    if request.GET.get("cerrar"):
        actualizar_demanda_real(request.GET["cerrar"])
        messages.info(request, "Demanda real contrastada con las predicciones.")
        return redirect("analitica:predicciones")
    lista = PrediccionDemanda.objects.select_related("materia")
    return render(request, "analitica/predicciones.html", {
        "predicciones": lista,
        "errores": [p for p in lista if p.error_absoluto() is not None],
    })
