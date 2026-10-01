# =====================================================================
# App anuncios: cartelera institucional con vigencia opcional.
# Publican: DOCENTE, SECRETARIA, DEPARTAMENTO (ADMIN siempre pasa).
# Ven: todos los roles (dashboard) + visitantes (login).
# Tipos: TEXTO, IMAGEN, URL, VIDEO, DOCUMENTO. Vigencia opcional
# (visible_desde / visible_hasta); sin fechas = siempre visible.
# =====================================================================
from django.conf import settings
from django.db import models
from django.utils import timezone


class Anuncio(models.Model):
    """Cartelera institucional con vigencia opcional y varios formatos."""

    class Tipo(models.TextChoices):
        TEXTO = "TEXTO", "Texto"
        IMAGEN = "IMAGEN", "Imagen"
        URL = "URL", "Enlace"
        VIDEO = "VIDEO", "Video"
        DOCUMENTO = "DOCUMENTO", "Documento"

    titulo = models.CharField(max_length=150)
    cuerpo = models.TextField(
        blank=True,
        help_text="Texto del anuncio o descripción del adjunto/enlace.",
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.TEXTO)
    enlace = models.URLField(
        "enlace", max_length=500, blank=True,
        help_text="Enlace externo: URL (sitio), video (YouTube/Drive) o imagen alojada.",
    )
    archivo = models.FileField(
        upload_to="anuncios/", blank=True, null=True,
        help_text="Para tipo Imagen, Video o Documento.",
    )
    roles = models.CharField(
        max_length=120, blank=True, default="",
        help_text="Roles destino separados por coma (vacío = todos). Ej.: ESTUDIANTE,DOCENTE",
    )
    visible_desde = models.DateTimeField(
        null=True, blank=True,
        help_text="Opcional: inicio de la vigencia.",
    )
    visible_hasta = models.DateTimeField(
        null=True, blank=True,
        help_text="Opcional: fin de la vigencia. Vacío = sin límite.",
    )
    activo = models.BooleanField(default=True, db_index=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="anuncios",
    )
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        # -pk desempata cuando dos anuncios comparten microsegundo en `creado`:
        # sin él el orden queda indefinido y el más nuevo podría no abrir.
        ordering = ["-creado", "-pk"]
        verbose_name = "anuncio"
        verbose_name_plural = "anuncios"

    def __str__(self):
        return f"{self.titulo} ({self.get_tipo_display()})"

    @property
    def roles_lista(self):
        return [r.strip().upper() for r in (self.roles or "").split(",") if r.strip()]

    # Icono de Bootstrap Icons según el tipo: usado por la cartelera (chip)
    # y por la lista de anuncios, para no repetir {% if %} en las plantillas.
    ICONOS = {
        Tipo.TEXTO: "bi-megaphone",
        Tipo.IMAGEN: "bi-image",
        Tipo.URL: "bi-link-45deg",
        Tipo.VIDEO: "bi-play-btn",
        Tipo.DOCUMENTO: "bi-file-earmark-text",
    }

    @property
    def icono(self):
        return self.ICONOS.get(self.tipo, "bi-megaphone")

    @property
    def fecha_corta(self):
        """Fecha compacta para la lista de la cartelera (ej. 24/09)."""
        return timezone.localtime(self.creado).strftime("%d/%m")

    def vigente(self, momento=None):
        momento = momento or timezone.now()
        if not self.activo:
            return False
        if self.visible_desde and momento < self.visible_desde:
            return False
        if self.visible_hasta and momento > self.visible_hasta:
            return False
        return True

    def visible_para(self, rol, momento=None):
        if not self.vigente(momento):
            return False
        if not self.roles_lista:
            return True
        return (rol or "").upper() in self.roles_lista

    @staticmethod
    def visibles(rol=None, momento=None):
        momento = momento or timezone.now()
        qs = Anuncio.objects.filter(activo=True)
        if momento:
            qs = qs.filter(
                models.Q(visible_desde__isnull=True) | models.Q(visible_desde__lte=momento),
                models.Q(visible_hasta__isnull=True) | models.Q(visible_hasta__gte=momento),
            )
        anuncios = list(qs.order_by("-creado", "-pk"))
        if rol:
            anuncios = [a for a in anuncios if a.visible_para(rol, momento)]
        return anuncios

