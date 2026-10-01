# =====================================================================
# Context processors: datos transversales a todas las plantillas.
# =====================================================================
from anuncios.models import Anuncio


def anuncios_carrusel(request):
    """Inyecta los anuncios vigentes en cualquier plantilla.

    - Con sesión iniciada: filtra por el rol del usuario.
    - Visitante (login): solo los anuncios sin restricción de rol.
    Los filtros de vigencia (visible_desde/hasta) se aplican siempre.
    """
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated:
        anuncios = Anuncio.visibles(rol=getattr(usuario, "rol", None))
    else:
        anuncios = [a for a in Anuncio.visibles() if not a.roles_lista]
    return {"anuncios_carrusel": anuncios}
