# =====================================================================
# Motor analítico: detección de necesidades, score (I×U)/(E+ε) y
# predicción de demanda (RF-51 a RF-56 · Cap. 6)
# =====================================================================
from collections import Counter

from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import NecesidadDetectada, PrediccionDemanda


def _periodo_siguiente(periodo):
    """Calcula el periodo siguiente del formato AAAA-N."""
    try:
        anio, numero = periodo.split("-")
        numero = int(numero)
    except (ValueError, AttributeError):
        return f"{timezone.localdate().year}-1"
    return f"{int(anio) + 1}-1" if numero >= 2 else f"{anio}-{numero + 1}"


def detectar_necesidades_de_quejas(periodo="", minimo=3):
    """RF-51: categorías de queja con recurrencia alta y baja satisfacción."""
    from quejas.models import Queja

    detectadas = []
    grupos = (Queja.objects.values("categoria__nombre", "categoria_id")
              .annotate(total=Count("id"), satisfaccion=Avg("satisfaccion")))
    for grupo in grupos:
        if grupo["total"] < minimo:
            continue
        satisfaccion = grupo["satisfaccion"] or 0
        impacto = ("CRITICO" if grupo["total"] >= minimo * 3 or satisfaccion < 2
                   else "ALTO" if grupo["total"] >= minimo * 2 else "MEDIO")
        necesidad, _ = NecesidadDetectada.objects.update_or_create(
            titulo=f"Quejas recurrentes: {grupo['categoria__nombre']}",
            periodo=periodo,
            defaults={
                "origen": NecesidadDetectada.Origen.QUEJAS,
                "impacto": impacto,
                "urgencia": NecesidadDetectada.Urgencia.ADMINISTRATIVA,
                "esfuerzo": 8.0,
                "descripcion": (f"{grupo['total']} casos en la categoría "
                                f"{grupo['categoria__nombre']}."),
                "evidencia": {"casos": grupo["total"],
                              "satisfaccion_promedio": round(satisfaccion, 2)},
            },
        )
        detectadas.append(necesidad)
    return detectadas


def detectar_necesidades_de_cupos(periodo="", minimo_solicitudes=5):
    """RF-51: materias con demanda insatisfecha (lista de espera alta)."""
    from cupos.models import SolicitudCupo

    detectadas = []
    grupos = (SolicitudCupo.objects
              .values("oferta__materia__nombre", "oferta__materia__codigo")
              .annotate(espera=Count("id", filter=Q(estado=SolicitudCupo.Estado.EN_ESPERA)),
                        total=Count("id")))
    for grupo in grupos:
        if grupo["espera"] < minimo_solicitudes:
            continue
        impacto = "CRITICO" if grupo["espera"] >= minimo_solicitudes * 2 else "ALTO"
        necesidad, _ = NecesidadDetectada.objects.update_or_create(
            titulo=f"Cupos insuficientes: {grupo['oferta__materia__nombre']}",
            periodo=periodo,
            defaults={
                "origen": NecesidadDetectada.Origen.CUPOS,
                "impacto": impacto,
                "urgencia": NecesidadDetectada.Urgencia.ADMINISTRATIVA,
                "esfuerzo": 12.0,
                "descripcion": (f"{grupo['espera']} estudiantes en lista de espera de "
                                f"{grupo['oferta__materia__nombre']}."),
                "evidencia": {"en_espera": grupo["espera"],
                              "solicitudes": grupo["total"]},
            },
        )
        detectadas.append(necesidad)
    return detectadas


def detectar_necesidades_de_inasistencia(periodo="", umbral=None):
    """RF-51: materias con inasistencia crítica recurrente (RN-08)."""
    from django.conf import settings

    from evaluaciones.models import ResumenInasistencia

    umbral = umbral or settings.SGDIC_UMBRAL_INASISTENCIA
    detectadas = []
    grupos = (ResumenInasistencia.objects.filter(riesgo=ResumenInasistencia.Riesgo.CRITICO)
              .values("oferta__materia__nombre", "oferta__materia__codigo")
              .annotate(casos=Count("id"), promedio=Avg("porcentaje")))
    for grupo in grupos:
        necesidad, _ = NecesidadDetectada.objects.update_or_create(
            titulo=f"Inasistencia elevada: {grupo['oferta__materia__nombre']}",
            periodo=periodo,
            defaults={
                "origen": NecesidadDetectada.Origen.INASISTENCIA,
                "impacto": "ALTO",
                "urgencia": NecesidadDetectada.Urgencia.DOCENTE,
                "esfuerzo": 6.0,
                "descripcion": (f"{grupo['casos']} estudiantes sobre el umbral de "
                                f"{umbral}% en {grupo['oferta__materia__nombre']}."),
                "evidencia": {"casos": grupo["casos"],
                              "porcentaje_promedio": round(grupo["promedio"] or 0, 2)},
            },
        )
        detectadas.append(necesidad)
    return detectadas


def detectar_necesidades_de_evaluacion(periodo="", minimo_respuestas=5, umbral=3.0):
    """RF-51: docentes con evaluación por debajo del promedio institucional."""
    from evaluaciones.models import RespuestaEvaluacion

    detectadas = []
    grupos = (RespuestaEvaluacion.objects
              .values("docente__username", "materia__nombre")
              .annotate(promedio=Avg("puntuacion"), total=Count("id")))
    for grupo in grupos:
        if grupo["total"] < minimo_respuestas or grupo["promedio"] >= umbral:
            continue
        necesidad, _ = NecesidadDetectada.objects.update_or_create(
            titulo=(f"Acompañamiento docente: {grupo['docente__username']} · "
                    f"{grupo['materia__nombre']}"),
            periodo=periodo,
            defaults={
                "origen": NecesidadDetectada.Origen.EVALUACION,
                "impacto": "ALTO",
                "urgencia": NecesidadDetectada.Urgencia.DOCENTE,
                "esfuerzo": 20.0,
                "descripcion": (f"Promedio de {grupo['promedio']:.2f}/5 con "
                                f"{grupo['total']} respuestas."),
                "evidencia": {"promedio": round(grupo["promedio"], 2),
                              "respuestas": grupo["total"], "umbral": umbral},
            },
        )
        detectadas.append(necesidad)
    return detectadas


def ejecutar_deteccion(periodo=None):
    """RF-52: ejecuta todos los detectores y devuelve el consolidado."""
    periodo = periodo or f"{timezone.localdate().year}-{1 if timezone.localdate().month <= 6 else 2}"
    resultados = {
        "quejas": detectar_necesidades_de_quejas(periodo),
        "cupos": detectar_necesidades_de_cupos(periodo),
        "inasistencia": detectar_necesidades_de_inasistencia(periodo),
        "evaluacion": detectar_necesidades_de_evaluacion(periodo),
    }
    total = sum(len(v) for v in resultados.values())
    return {"periodo": periodo, "total": total, "detalle": resultados,
            "necesidades": NecesidadDetectada.objects.filter(periodo=periodo)}


# ------------------------- Predicción (RF-54/RF-55) -------------------------
def _serie_historica(materia):
    """Serie de ocupación (inscritos) por periodo de una materia."""
    from cupos.models import OfertaCupo

    ofertas = OfertaCupo.objects.filter(materia=materia).order_by("periodo")
    return [(o.periodo, o.inscritos) for o in ofertas]


def _promedio_movil(valores, ventana=3):
    """Promedio móvil de los últimos `ventana` periodos."""
    muestra = valores[-ventana:]
    return sum(muestra) / len(muestra) if muestra else 0


def _regresion_lineal(valores):
    """Regresión lineal simple y = a + b·x; devuelve (a, b, confianza)."""
    n = len(valores)
    if n < 2:
        return (valores[0] if valores else 0), 0, 0.0
    xs = list(range(n))
    media_x = sum(xs) / n
    media_y = sum(valores) / n
    varianza_x = sum((x - media_x) ** 2 for x in xs)
    covarianza = sum((x - media_x) * (y - media_y) for x, y in zip(xs, valores))
    pendiente = covarianza / varianza_x if varianza_x else 0
    intercepto = media_y - pendiente * media_x
    varianza_y = sum((y - media_y) ** 2 for y in valores)
    r2 = (covarianza ** 2) / (varianza_x * varianza_y) if varianza_x and varianza_y else 0
    return intercepto, pendiente, round(r2, 3)


def predecir_materia(materia, periodo_objetivo=None, ventana=3):
    """RF-54: estima la demanda del próximo periodo y sugiere cupo."""
    serie = _serie_historica(materia)
    if not serie:
        return None
    valores = [v for _, v in serie]
    ultimo_periodo = serie[-1][0]
    periodo_objetivo = periodo_objetivo or _periodo_siguiente(ultimo_periodo)
    mm = _promedio_movil(valores, ventana)
    intercepto, pendiente, r2 = _regresion_lineal(valores)
    proyeccion = max(intercepto + pendiente * len(valores), 0)
    if r2 >= 0.5:
        estimada = proyeccion
        metodo = PrediccionDemanda.Metodo.REGRESION
        confianza = r2
    else:
        estimada = mm
        metodo = PrediccionDemanda.Metodo.PROMEDIO_MOVIL
        confianza = round(1 - r2, 3)
    prediccion, _ = PrediccionDemanda.objects.update_or_create(
        materia=materia, periodo_objetivo=periodo_objetivo,
        defaults={
            "demanda_estimada": round(estimada, 2),
            "cupo_sugerido": max(int(round(estimada * 1.1)), 1),
            "metodo": metodo,
            "confianza": confianza,
            "detalle": {"serie": dict(serie), "promedio_movil": round(mm, 2),
                        "pendiente": round(pendiente, 3), "r2": r2},
        },
    )
    return prediccion


def predecir_todas(periodo_objetivo=None):
    """RF-54: genera predicciones para todas las materias con histórico."""
    from materias.models import Materia

    generadas = []
    for materia in Materia.objects.filter(ofertas__isnull=False).distinct():
        prediccion = predecir_materia(materia, periodo_objetivo)
        if prediccion:
            generadas.append(prediccion)
    return generadas


def actualizar_demanda_real(periodo):
    """RF-55: contrasta la predicción con la demanda real del periodo cerrado."""
    from cupos.models import OfertaCupo

    for prediccion in PrediccionDemanda.objects.filter(periodo_objetivo=periodo):
        oferta = OfertaCupo.objects.filter(
            materia=prediccion.materia, periodo=periodo).first()
        if oferta:
            prediccion.demanda_real = oferta.inscritos
            prediccion.save(update_fields=["demanda_real"])
    return PrediccionDemanda.objects.filter(periodo_objetivo=periodo)


