from django.contrib import admin

from .models import PlantillaReporte, ProgramacionReporte, ReporteGenerado


@admin.register(PlantillaReporte)
class PlantillaReporteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "activa", "creada")
    list_filter = ("tipo", "activa")
    search_fields = ("nombre", "descripcion")


@admin.register(ReporteGenerado)
class ReporteGeneradoAdmin(admin.ModelAdmin):
    list_display = ("plantilla", "solicitado_por", "formato", "estado",
                    "total_registros", "creado")
    list_filter = ("estado", "formato")
    readonly_fields = ("contenido", "mensaje_error", "generado")


@admin.register(ProgramacionReporte)
class ProgramacionReporteAdmin(admin.ModelAdmin):
    list_display = ("plantilla", "frecuencia", "formato", "activa",
                    "ultima_ejecucion", "proxima_ejecucion")
    list_filter = ("frecuencia", "activa")
    filter_horizontal = ("destinatarios",)
