from django import forms

from usuario.models import ROLES

from .models import Anuncio


def _estilizar(form):
    for campo in form.fields.values():
        widget = campo.widget
        if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
            widget.attrs.setdefault("class", "form-check-input")
        else:
            widget.attrs.setdefault("class", "form-control")
    return form


class AnuncioForm(forms.ModelForm):
    """Publicación de cartelera: texto, imagen, enlace, video o documento."""

    roles_destino = forms.MultipleChoiceField(
        choices=ROLES, required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="Visible para (vacío = todos los roles)",
    )

    class Meta:
        model = Anuncio
        fields = ["titulo", "tipo", "cuerpo", "enlace", "archivo",
                  "visible_desde", "visible_hasta", "activo"]
        widgets = {
            "cuerpo": forms.Textarea(attrs={"rows": 4}),
            "visible_desde": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "visible_hasta": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self)
        if self.instance and self.instance.pk and self.instance.roles:
            self.fields["roles_destino"].initial = self.instance.roles_lista

    def save(self, commit=True):
        obj = super().save(commit=False)
        elegidos = self.cleaned_data.get("roles_destino") or []
        obj.roles = ",".join(elegidos)
        if commit:
            obj.save()
        return obj
