# =====================================================================
# Middleware propio: expone la configuración de negocio (settings.SGDIC_*)
# y utilidades de contexto en cada request.
# =====================================================================
from django.conf import settings


class ConfiguracionSGDIC:
    """Añade `request.sgdic_config` con los parámetros de negocio."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.sgdic_config = {
            "umbral_inasistencia": settings.SGDIC_UMBRAL_INASISTENCIA,
            "horas_respuesta": settings.SGDIC_HORAS_RESPUESTA,
            "dias_escalamiento": settings.SGDIC_DIAS_ESCALAMIENTO,
            "min_respuestas_anonimo": settings.SGDIC_MIN_RESPUESTAS_ANONIMO,
        }
        return self.get_response(request)
