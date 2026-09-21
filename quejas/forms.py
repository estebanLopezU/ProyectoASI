from django import forms

from usuario.models import Usuario

from .models import CategoriaQueja, Queja


def _estilizar(form):
    for campo in form.fields.values():
        widget = campo.widget
        if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
            widget.attrs.setdefault("class", "form-check-input")
        else:
            widget.attrs.setdefault("class", "form-control")
    return form


class QuejaForm(forms.ModelForm):
    """RF-35/RF-36: radicación de queja, con opción anónima (RN-09)."""

    class Meta:
        model = Queja
        fields = ["categoria", "materia", "asunto", "descripcion", "evidencia",
                  "anonima", "prioridad"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaQueja.objects.filter(activa=True)
        self.fields["materia"].required = False
        _estilizar(self)


class GestionQuejaForm(forms.Form):
    """RF-37 a RF-39: asignar, comentar, resolver o escalar."""

    ACCIONES = [
        ("AVANCE", "Registrar avance"),
        ("ASIGNAR", "Asignar a gestor"),
        ("RESOLVER", "Marcar como resuelto"),
        ("SOLUCION_RAPIDA", "Aplicar solución rápida (RN-11)"),
        ("ESCALAR", "Escalar al departamento"),
    ]

    accion = forms.ChoiceField(choices=ACCIONES)
    gestor = forms.ModelChoiceField(queryset=Usuario.objects.none(), required=False)
    detalle = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}),
                             label="Detalle / solución")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["gestor"].queryset = Usuario.objects.filter(
            rol__in=("DEPARTAMENTO", "SECRETARIA", "DOCENTE"))
        _estilizar(self)


class CierreForm(forms.Form):
    """RN-12/RF-42: el usuario confirma el cierre y califica."""

    satisfaccion = forms.ChoiceField(
        choices=[(n, f"{n} - {'Excelente' if n == 5 else 'Muy bueno' if n == 4 else 'Aceptable' if n == 3 else 'Regular' if n == 2 else 'Deficiente'}")
                 for n in range(5, 0, -1)],
        label="Califique la atención recibida",
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self)


class EscalamientoMasivoForm(forms.Form):
    """RF-38: revisión de casos vencidos (RN-10)."""

    casos = forms.ModelMultipleChoiceField(
        queryset=Queja.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple, label="Casos a escalar",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["casos"].queryset = Queja.objects.exclude(
            estado__in=(Queja.Estado.RESUELTO, Queja.Estado.CERRADO,
                        Queja.Estado.ESCALADO))
        _estilizar(self)
