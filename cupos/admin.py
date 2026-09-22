from django.contrib import admin

from .models import Inscripcion, OfertaCupo, Preinscripcion, SolicitudCupo


@admin.register(OfertaCupo)
class OfertaCupoAdmin(admin.ModelAdmin):
    list_display = ("materia", "periodo", "grupo", "docente", "cupo_maximo",
                    "inscritos", "dia", "hora_inicio", "hora_fin", "activa")
    list_filter = ("periodo", "activa", "dia", "materia")
    search_fields = ("materia__codigo", "materia__nombre", "grupo")


@admin.register(Preinscripcion)
class PreinscripcionAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "materia", "grupo", "prioridad",
                    "periodo_objetivo", "probabilidad", "estado")
    list_filter = ("periodo_objetivo", "estado", "prioridad")
    search_fields = ("estudiante__username", "materia__codigo")
    autocomplete_fields = ("grupo",)



@admin.register(SolicitudCupo)
class SolicitudCupoAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "oferta", "estado", "prioridad", "creada")
    list_filter = ("estado", "oferta__periodo")
    search_fields = ("estudiante__username", "oferta__materia__codigo")


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "oferta", "estado", "confirmada", "creada")
    list_filter = ("estado", "oferta__periodo")
