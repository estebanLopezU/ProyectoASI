from django import forms

from usuario.models import Usuario

from .models import Hilo, Mensaje


class NuevoHiloForm(forms.ModelForm):
    """RF-16: hilo nuevo del estudiante hacia un docente de sus materias."""

    contenido = forms.CharField(label="Mensaje", widget=forms.Textarea(attrs={"rows": 4}))

    class Meta:
        model = Hilo
        fields = ["docente", "materia", "asunto", "tipo"]

    def __init__(self, *args, estudiante=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.estudiante = estudiante
        if estudiante:
            materia_ids = list(
                estudiante.inscripciones.filter(estado="ACTIVA")
                .values_list("oferta__materia_id", flat=True)
            )
        else:
            materia_ids = []
        self.fields["docente"].queryset = Usuario.objects.filter(rol="DOCENTE")
        self.fields["materia"].queryset = (
            Hilo._meta.get_field("materia").related_model.objects.filter(pk__in=materia_ids)
        )
        self.fields["materia"].required = False
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "form-control")

    def save(self, commit=True):
        hilo = super().save(commit=False)
        hilo.estudiante = self.estudiante
        if commit:
            hilo.save()
        return hilo


class MensajeForm(forms.ModelForm):
    class Meta:
        model = Mensaje
        fields = ["contenido"]
        widgets = {"contenido": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contenido"].widget.attrs.setdefault("class", "form-control")

