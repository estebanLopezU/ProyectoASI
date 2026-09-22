import json

from django import forms

from .models import MallaCurricular, Materia, SolicitudMateria


class SolicitudMateriaForm(forms.Form):
    """Formulario para propuesta de creación (RF-11) o edición (RF-12)."""

    codigo_nuevo = forms.CharField(
        label="Código", max_length=12,
        help_text="Solo para creación de materia nueva."
    )
    nombre = forms.CharField(label="Nombre", max_length=120)
    creditos = forms.IntegerField(label="Créditos", min_value=1, max_value=12, initial=3)
    cupo_maximo = forms.IntegerField(label="Cupo máximo", min_value=1, max_value=300, initial=30)
    justificacion = forms.CharField(
        label="Justificación", widget=forms.Textarea(attrs={"rows": 4})
    )
    propuesta_json = forms.CharField(
        label="Cambios propuestos (JSON)", required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text='Opcional en ediciones. Ej.: {"nombre": "Nuevo nombre"}'
    )

    def __init__(self, *args, materia=None, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "form-control")
        if materia:
            self.fields["codigo_nuevo"].widget = forms.HiddenInput()
            self.fields["codigo_nuevo"].required = False
            self.fields["nombre"].initial = materia.nombre
            self.fields["creditos"].initial = materia.creditos
            self.fields["cupo_maximo"].initial = materia.cupo_maximo

    def clean_codigo_nuevo(self):
        codigo = self.cleaned_data.get("codigo_nuevo", "").strip().upper()
        if codigo and Materia.objects.filter(codigo=codigo).exists():
            raise forms.ValidationError("Ya existe una materia con ese código.")
        return codigo

    def clean_propuesta_json(self):
        texto = (self.cleaned_data.get("propuesta_json") or "").strip()
        if not texto:
            return {}
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError:
            raise forms.ValidationError("El JSON de cambios no es válido.")
        if not isinstance(datos, dict):
            raise forms.ValidationError("El JSON de cambios debe ser un objeto.")
        return datos

    def propuesta(self):
        """RF-12: consolida los cambios a aplicar sobre la materia existente."""
        cambios = dict(self.cleaned_data.get("propuesta_json") or {})
        for campo in ("nombre", "creditos", "cupo_maximo"):
            valor = self.cleaned_data.get(campo)
            if valor and cambios.get(campo) != valor:
                cambios[campo] = valor
        return cambios


class MallaCurricularForm(forms.ModelForm):
    """Formulario para que el administrativo ubique la materia en la malla."""

    class Meta:
        model = MallaCurricular
        fields = ("semestre", "estado", "observacion")
        widgets = {
            "semestre": forms.NumberInput(attrs={
                "class": "form-control", "min": 1, "max": 10}),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "observacion": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej. Regularizada en 2025-2"}),
        }
        labels = {
            "semestre": "Semestre del plan (1-10)",
            "estado": "Estado en la malla",
            "observacion": "Observación",
        }
        help_texts = {
            "estado": ("Automático = derivado de las inscripciones "
                       "(verde aprobada, amarilla en curso, roja pendiente)."),
        }

    def clean_semestre(self):
        semestre = self.cleaned_data.get("semestre")
        if semestre is None or not 1 <= semestre <= 10:
            raise forms.ValidationError("El semestre debe estar entre 1 y 10.")
        return semestre