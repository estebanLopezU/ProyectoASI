from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "rol", "is_active")
    list_filter = ("rol", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Datos SGDIC", {"fields": ("rol", "telefono", "codigo_institucional")}),
        ("Información académica", {"fields": ("area", "semestre", "promedio")}),
        ("Preferencias", {"fields": ("notificar_correo",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos SGDIC", {"fields": ("rol", "telefono", "codigo_institucional")}),
    )
    search_fields = ("username", "first_name", "last_name", "email",
                     "codigo_institucional")
