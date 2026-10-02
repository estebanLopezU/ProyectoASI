# =====================================================================
# Registro en el Django admin.
# =====================================================================
from django.contrib import admin

from .models import Grupo, Inscripcion


@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "coordinador", "miembros_count",
                    "cupo", "activo")
    list_filter = ("tipo", "activo")
    search_fields = ("nombre", "linea", "descripcion")


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ("grupo", "usuario", "estado", "creada", "respondida")
    list_filter = ("estado",)
    search_fields = ("grupo__nombre", "usuario__username")
    raw_id_fields = ("grupo", "usuario")