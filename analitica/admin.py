from django.contrib import admin

from .models import NecesidadDetectada, PrediccionDemanda


@admin.register(NecesidadDetectada)
class NecesidadDetectadaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "origen", "impacto", "urgencia", "esfuerzo",
                    "score", "periodo")
    list_filter = ("origen", "impacto", "urgencia", "periodo")
    search_fields = ("titulo", "descripcion")
    readonly_fields = ("score", "creada", "actualizada")


@admin.register(PrediccionDemanda)
class PrediccionDemandaAdmin(admin.ModelAdmin):
    list_display = ("materia", "periodo_objetivo", "demanda_estimada",
                    "demanda_real", "cupo_sugerido", "metodo", "confianza")
    list_filter = ("metodo", "periodo_objetivo")
    search_fields = ("materia__nombre", "materia__codigo")
    readonly_fields = ("generada",)
