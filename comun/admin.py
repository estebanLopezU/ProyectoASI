from django.contrib import admin

from .models import AuditoriaLog, Notificacion


@admin.register(AuditoriaLog)
class AuditoriaLogAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "objeto_tipo", "objeto_id")
    list_filter = ("accion", "objeto_tipo")
    search_fields = ("detalle", "usuario__username")
    readonly_fields = ("usuario", "accion", "objeto_tipo", "objeto_id", "detalle", "fecha")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("creada", "destinatario", "titulo", "nivel", "leida")
    list_filter = ("nivel", "leida")
    search_fields = ("titulo", "cuerpo", "destinatario__username")
