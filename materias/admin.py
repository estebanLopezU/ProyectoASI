from django.contrib import admin

from .models import Materia, SolicitudMateria, VersionMateria


class VersionInline(admin.TabularInline):
    model = VersionMateria
    extra = 0
    readonly_fields = ("version", "autor", "fecha")


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "creditos", "cupo_maximo", "estado")
    list_filter = ("estado",)
    search_fields = ("codigo", "nombre")
    inlines = [VersionInline]


@admin.register(SolicitudMateria)
class SolicitudMateriaAdmin(admin.ModelAdmin):
    list_display = ("materia", "tipo", "estado", "solicitante", "creado")
    list_filter = ("tipo", "estado")
