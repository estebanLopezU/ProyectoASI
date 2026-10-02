# =====================================================================
# Formularios de grupos de investigación y semilleros.
# =====================================================================
from django import forms
from django.core.exceptions import ValidationError

from comun.widgets import estilizar_campo
from usuario.models import Usuario

from .models import Grupo, Inscripcion


class GrupoForm(forms.ModelForm):
    """Crear/editar un grupo. El coordinador siempre es un docente."""

    class Meta:
        model = Grupo
        fields = ["nombre", "tipo", "descripcion", "linea", "coordinador",
                  "cupo", "activo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        self.creador = kwargs.pop("creador", None)
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            estilizar_campo(campo.widget)
        # Solo docentes pueden coordinar (deben aprobar solicitudes).
        self.fields["coordinador"].queryset = Usuario.objects.filter(rol="DOCENTE")
        self.fields["coordinador"].required = False
        self.fields["cupo"].required = False

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise ValidationError("Escribe un nombre para el grupo.")
        return nombre

    def clean_cupo(self):
        cupo = self.cleaned_data.get("cupo")
        if cupo is not None and cupo < 1:
            raise ValidationError("El cupo debe ser al menos 1, o vacío si es sin límite.")
        return cupo

    def clean(self):
        super().clean()
        coordinador = self.cleaned_data.get("coordinador")
        # Si publica un docente y no elige coordinador, él mismo queda a cargo.
        if not coordinador and self.creador is not None \
                and getattr(self.creador, "rol", None) == "DOCENTE":
            self.cleaned_data["coordinador"] = self.creador
            self.instance.coordinador = self.creador
        elif not coordinador:
            self.add_error(
                "coordinador",
                "Elige un docente como coordinador: es quien aprueba las solicitudes.",
            )
        return self.cleaned_data


class SolicitudForm(forms.ModelForm):
    """Solicitud de ingreso de un estudiante/docente a un grupo."""

    class Meta:
        model = Inscripcion
        fields = ["respuesta"]
        labels = {"respuesta": "¿Por qué te interesa este grupo? (opcional)"}
        widgets = {"respuesta": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            estilizar_campo(campo.widget)
        self.fields["respuesta"].required = False