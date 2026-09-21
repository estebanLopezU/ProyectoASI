from django.contrib import admin

from .models import CategoriaQueja, Queja, Seguimiento


@admin.register(CategoriaQueja)
class CategoriaQuejaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa", "tiene_solucion")
    list_filter = ("activa",)

    @admin.display(boolean=True, description="solución rápida")
    def tiene_solucion(self, obj):
        return bool(obj.solucion_rapida)


class SeguimientoInline(admin.TabularInline):
    model = Seguimiento
    extra = 0
    readonly_fields = ("creado",)


@admin.register(Queja)
class QuejaAdmin(admin.ModelAdmin):
    list_display = ("consecutivo", "asunto", "categoria", "estado", "prioridad",
                    "gestor", "creada")
    list_filter = ("estado", "prioridad", "categoria", "anonima")
    search_fields = ("consecutivo", "asunto", "descripcion")
    readonly_fields = ("consecutivo", "creada", "actualizada", "escalada", "resuelta")
    inlines = [SeguimientoInline]


@admin.register(Seguimiento)
class SeguimientoAdmin(admin.ModelAdmin):
    list_display = ("queja", "tipo", "autor", "creado")
    list_filter = ("tipo",)
