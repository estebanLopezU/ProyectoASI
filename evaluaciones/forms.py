from django import forms

from usuario.models import Usuario

from .models import Falta, InvitacionEvaluacion, PeriodoEvaluacion, Sesion


class SesionForm(forms.ModelForm):
    class Meta:
        model = Sesion
        fields = ["fecha", "tema"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "form-control")


class RegistroFaltasForm(forms.Form):
    """Asistencia de una sesión: marca los estudiantes ausentes."""

    ausentes = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple, label="Estudiantes ausentes",
    )
    motivo = forms.CharField(max_length=200, required=False,
                             widget=forms.TextInput(attrs={"class": "form-control"}))

    def __init__(self, *args, oferta=None, **kwargs):
        super().__init__(*args, **kwargs)
        if oferta:
            self.fields["ausentes"].queryset = Usuario.objects.filter(
                inscripciones__oferta=oferta, inscripciones__estado="ACTIVA"
            ).distinct()


class JustificacionForm(forms.ModelForm):
    class Meta:
        model = Falta
        fields = ["comentario_justificacion", "evidencia"]
        widgets = {"comentario_justificacion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comentario_justificacion"].required = True
        self.fields["comentario_justificacion"].label = "Motivo de la justificación"
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "form-control")


class RevisionJustificacionForm(forms.Form):
    aprobada = forms.BooleanField(required=False, label="Aprobar justificación")
    comentario = forms.CharField(max_length=300, required=False,
                                 widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "form-control")


class PeriodoEvaluacionForm(forms.ModelForm):
    class Meta:
        model = PeriodoEvaluacion
        fields = ["nombre", "fecha_inicio", "fecha_limite", "activo",
                  "bloquear_servicios", "umbral_participacion"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_limite": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        datos = super().clean()
        inicio, limite = datos.get("fecha_inicio"), datos.get("fecha_limite")
        if inicio and limite and limite < inicio:
            raise forms.ValidationError("La fecha límite no puede ser anterior al inicio.")
        return datos


class RespuestaEvaluacionForm(forms.Form):
    """Formulario anónimo dinámico según las preguntas del periodo (RF-30)."""

    def __init__(self, *args, preguntas=None, **kwargs):
        super().__init__(*args, **kwargs)
        for i, texto in enumerate(preguntas or []):
            self.fields[f"pregunta_{i}"] = forms.ChoiceField(
                label=texto,
                choices=[(n, str(n)) for n in range(1, 6)],
                widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
            )
        self.fields["comentario"] = forms.CharField(
            required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"})
        )

    def puntuaciones(self):
        return [
            int(valor) for clave, valor in self.cleaned_data.items()
            if clave.startswith("pregunta_")
        ]

    def promedio(self):
        notas = self.puntuaciones()
        return round(sum(notas) / len(notas), 2) if notas else 0.0
