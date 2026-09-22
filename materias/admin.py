from django.contrib import admin

from .models import MallaCurricular, Materia, SolicitudMateria, VersionMateria


class VersionInline(admin.TabularInline):
    model = VersionMateria
    extra = 0
    readonly_fields = ("version", "autor", "fecha")


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "creditos", "cupo_maximo",
                    "semestre", "estado")
    list_filter = ("estado", "semestre")
    search_fields = ("codigo", "nombre")
    inlines = [VersionInline]


@admin.register(SolicitudMateria)
class SolicitudMateriaAdmin(admin.ModelAdmin):
    list_display = ("materia", "tipo", "estado", "solicitante", "creado")
    list_filter = ("tipo", "estado")


@admin.register(MallaCurricular)
class MallaCurricularAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "materia", "semestre", "estado",
                    "actualizado_por", "actualizado")
    list_filter = ("semestre", "estado")
    search_fields = ("estudiante__username", "estudiante__first_name",
                     "materia__codigo", "materia__nombre")
    raw_id_fields = ("estudiante", "materia")
