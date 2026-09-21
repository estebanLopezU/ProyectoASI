from django.contrib import admin

from .models import Inscripcion, OfertaCupo, SolicitudCupo


@admin.register(OfertaCupo)
class OfertaCupoAdmin(admin.ModelAdmin):
    list_display = ("materia", "periodo", "cupo_maximo", "inscritos", "dia",
                    "hora_inicio", "hora_fin", "activa")
    list_filter = ("periodo", "activa", "dia")


@admin.register(SolicitudCupo)
class SolicitudCupoAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "oferta", "estado", "prioridad", "creada")
    list_filter = ("estado", "oferta__periodo")
    search_fields = ("estudiante__username", "oferta__materia__codigo")


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "oferta", "estado", "confirmada", "creada")
    list_filter = ("estado", "oferta__periodo")
