from django.contrib import admin

from .models import (Falta, InvitacionEvaluacion, PeriodoEvaluacion,
                     ResumenInasistencia, RespuestaEvaluacion, Sesion)


@admin.register(Sesion)
class SesionAdmin(admin.ModelAdmin):
    list_display = ("oferta", "fecha", "tema", "registrada")
    list_filter = ("registrada", "oferta__periodo")
    search_fields = ("oferta__materia__codigo", "tema")


@admin.register(Falta)
class FaltaAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "sesion", "estado", "motivo", "registrada")
    list_filter = ("estado",)
    search_fields = ("estudiante__username", "estudiante__first_name")


@admin.register(ResumenInasistencia)
class ResumenInasistenciaAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "oferta", "faltas", "total_sesiones",
                    "porcentaje", "riesgo", "alerta_enviada")
    list_filter = ("riesgo", "alerta_enviada")


@admin.register(PeriodoEvaluacion)
class PeriodoEvaluacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "fecha_inicio", "fecha_limite", "activo",
                    "umbral_participacion", "bloquear_servicios")
    list_filter = ("activo",)


@admin.register(InvitacionEvaluacion)
class InvitacionEvaluacionAdmin(admin.ModelAdmin):
    list_display = ("periodo", "estudiante", "docente", "materia", "completada")
    list_filter = ("periodo", "completada")


@admin.register(RespuestaEvaluacion)
class RespuestaEvaluacionAdmin(admin.ModelAdmin):
    list_display = ("docente", "materia", "periodo", "puntuacion", "creado")
    list_filter = ("periodo", "materia")
    # No se expone ningún dato del autor: la respuesta es anónima (RN-05).
