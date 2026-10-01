# =====================================================================
# Widgets reutilizables con marcado Bootstrap 5
# =====================================================================
from django import forms


class CheckboxGrupoWidget(forms.CheckboxSelectMultiple):
    """Grupo de casillas con marcado Bootstrap 5 correcto.

    El widget nativo (checkbox_select.html -> multiple_input.html) imprime
    ``widget.attrs`` en el <div> contenedor. Si ahí hay ``form-check-input``
    —clase pensada para el <input>— Bootstrap le fija ``width/height: 1em``,
    el contenedor colapsa y las opciones se desbordan fuera del panel,
    encimándose con los botones del formulario.

    Además ``CheckboxSelectMultiple`` hereda de ``RadioSelect``, por lo que
    los ``_estilizar()`` de cada app lo clasifican como "casilla" y reparten
    esa clase a todo, con el efecto anterior.

    ``get_context()`` separa ambas responsabilidades:
      * contenedor -> ``grupo-checks`` (lo pinta la plantilla propia)
      * cada opción -> ``form-check-input``, así se ve bien tanto con el
        render directo ``{{ campo }}`` como iterando opción por opción
        (``{% for c in campo %}{{ c.tag }}{% endfor %}``), que es como
        lo pintan las plantillas de asistencia y de quejas.

    Plantilla: comun/templates/widgets/checkbox_grupo.html
    """

    template_name = "widgets/checkbox_grupo.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # El contenedor nunca lleva form-check-input: colapsa a 1em.
        context["widget"]["attrs"]["class"] = "grupo-checks"
        for _grupo, opciones, _indice in context["widget"]["optgroups"]:
            for opcion in opciones:
                opcion["attrs"]["class"] = "form-check-input"
        return context


def estilizar_campo(widget):
    """Clase de un widget suelto. Devuelve False si CheckboxGrupoWidget la
    asigna por su cuenta (contenedor e inputs llevan clases distintas y un
    simple setdefault no podría diferenciarlas)."""
    if isinstance(widget, CheckboxGrupoWidget):
        widget.attrs.pop("class", None)
        return False
    if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
        widget.attrs.setdefault("class", "form-check-input")
        return True
    widget.attrs.setdefault("class", "form-control")
    return True
