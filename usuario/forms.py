from django import forms

from .models import Usuario


class PerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email", "telefono", "codigo_institucional",
              "area", "semestre", "notificar_correo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notificar_correo"].widget.attrs["class"] = "form-check-input"
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "form-control")
