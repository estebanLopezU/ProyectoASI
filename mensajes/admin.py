from django.contrib import admin

from .models import Hilo, Mensaje


class MensajeInline(admin.TabularInline):
    model = Mensaje
    extra = 0
    readonly_fields = ("autor", "leido", "leido_en", "creado")


@admin.register(Hilo)
class HiloAdmin(admin.ModelAdmin):
    list_display = ("asunto", "estudiante", "docente", "tipo", "intervenido_por", "cerrado")
    list_filter = ("tipo", "cerrado")
    search_fields = ("asunto", "estudiante__username", "docente__username")
    inlines = [MensajeInline]


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ("hilo", "autor", "leido", "creado")
    list_filter = ("leido",)
