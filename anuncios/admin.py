from django.contrib import admin

from .models import Anuncio


@admin.register(Anuncio)
class AnuncioAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tipo", "activo", "visible_desde", "visible_hasta", "creado")
    list_filter = ("tipo", "activo")
    search_fields = ("titulo", "cuerpo")

