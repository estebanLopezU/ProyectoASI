# =====================================================================
# Context processors: datos transversales a todas las plantillas.
# =====================================================================
from anuncios.models import Anuncio

# Pestañas de la cartelera: (tipo de anuncio, etiqueta visible).
# El orden de esta lista define el orden de las pestañas en el banner.
GRUPOS_CARTELERA = [
    ("TEXTO", "Avisos"),
    ("IMAGEN", "Imágenes"),
    ("URL", "Enlaces"),
    ("VIDEO", "Videos"),
    ("DOCUMENTO", "Documentos"),
]


def anuncios_carrusel(request):
    """Inyecta los anuncios vigentes en cualquier plantilla.

    - Con sesión iniciada: filtra por el rol del usuario.
    - Visitante (login): solo los anuncios sin restricción de rol.
    Los filtros de vigencia (visible_desde/hasta) se aplican siempre.

    Devuelve además `anuncios_grupos`: la lista de pestañas (una por tipo
    presente). Sirve para el panel con pestañas + lista con fechas.
    """
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated:
        anuncios = Anuncio.visibles(rol=getattr(usuario, "rol", None))
    else:
        anuncios = [a for a in Anuncio.visibles() if not a.roles_lista]

    grupos = []
    for clave, etiqueta in GRUPOS_CARTELERA:
        total = sum(1 for a in anuncios if a.tipo == clave)
        if total:
            grupos.append({"clave": clave, "etiqueta": etiqueta, "total": total})

    # La primera pestaña debe ser la del anuncio más reciente: es el que abre
    # el banner, así la pestaña activa y la diapositiva visible coinciden.
    if anuncios and grupos:
        primero = anuncios[0].tipo
        grupos.sort(key=lambda g: g["clave"] != primero)

    return {"anuncios_carrusel": anuncios, "anuncios_grupos": grupos}
