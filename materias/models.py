# =====================================================================
# App materias: catálogo, versiones y flujo de aprobación
# RF-11 a RF-15, RN-11 (aprobación del departamento)
# =====================================================================
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class Materia(models.Model):
    """Unidad curricular (RF-14: historial de versiones)."""

    class Estado(models.TextChoices):
        PROPUESTA = "PROPUESTA", "Propuesta"
        EN_REVISION = "EN_REVISION", "En revisión"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        PUBLICADA = "PUBLICADA", "Publicada"

    codigo = models.CharField("código", max_length=12, unique=True)
    nombre = models.CharField("nombre", max_length=120)
    creditos = models.PositiveSmallIntegerField("créditos", default=3)
    cupo_maximo = models.PositiveSmallIntegerField("cupo máximo", default=30)
    prerrequisitos = models.ManyToManyField("self", blank=True, symmetrical=False,
                                            related_name="prerrequisito_de")
    estado = models.CharField("estado", max_length=12, choices=Estado.choices,
                              default=Estado.PROPUESTA)
    docentes = models.ManyToManyField("usuario.Usuario", blank=True,
                                      related_name="materias_dictadas",
                                      limit_choices_to={"rol": "DOCENTE"},
                                      verbose_name="docentes asignados")
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "materia"
        verbose_name_plural = "materias"

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    @property
    def publicada(self):
        return self.estado == self.Estado.PUBLICADA


class VersionMateria(models.Model):
    """Historial de versiones con autor y fecha (RF-14)."""

    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name="versiones")
    version = models.PositiveIntegerField("versión", default=1)
    contenido = models.TextField("contenido / justificación")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name="versiones_materia")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["materia", "-version"]
        verbose_name = "versión de materia"
        verbose_name_plural = "versiones de materia"

    def __str__(self):
        return f"{self.materia.codigo} v{self.version}"


class SolicitudMateria(models.Model):
    """Flujo propuesta → revisión → aprobación/rechazo → publicación (RF-13)."""

    class Tipo(models.TextChoices):
        CREACION = "CREACION", "Creación"
        EDICION = "EDICION", "Edición"

    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name="solicitudes")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    justificacion = models.TextField()
    propuesta = models.JSONField("propuesta de cambios", default=dict, blank=True)
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                    on_delete=models.SET_NULL, related_name="solicitudes_materia")
    estado = models.CharField(max_length=12, choices=Materia.Estado.choices,
                              default=Materia.Estado.PROPUESTA)
    comentario_revision = models.TextField(blank=True)
    revisor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="revisiones_materia")
    creado = models.DateTimeField(auto_now_add=True)
    resuelta = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "solicitud de materia"
        verbose_name_plural = "solicitudes de materia"

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.materia} · {self.estado}"

    # ---------------------------------------------------------------
    # Flujo de aprobación (RF-13, RN-11)
    # ---------------------------------------------------------------
    @transaction.atomic
    def aprobar(self, revisor):
        if self.estado not in (self.materia.Estado.PROPUESTA, self.materia.Estado.EN_REVISION):
            raise ValueError("La solicitud ya fue resuelta.")
        self.estado = self.materia.Estado.APROBADA
        self.revisor = revisor
        self.resuelta = timezone.now()
        self.save(update_fields=["estado", "revisor", "resuelta"])
        self._aplicar_cambios()

    @transaction.atomic
    def rechazar(self, revisor, comentario=""):
        if self.estado not in (self.materia.Estado.PROPUESTA, self.materia.Estado.EN_REVISION):
            raise ValueError("La solicitud ya fue resuelta.")
        self.estado = self.materia.Estado.RECHAZADA
        self.revisor = revisor
        self.comentario_revision = comentario
        self.resuelta = timezone.now()
        self.save(update_fields=["estado", "revisor", "comentario_revision", "resuelta"])

    def _aplicar_cambios(self):
        """Aplica los cambios propuestos y publica en el catálogo (RF-15)."""
        materia = self.materia
        for campo, valor in (self.propuesta or {}).items():
            if campo in ("codigo", "nombre", "creditos", "cupo_maximo") and valor:
                setattr(materia, campo, valor)
        materia.estado = materia.Estado.PUBLICADA
        materia.save()
        VersionMateria.objects.create(
            materia=materia,
            version=materia.versiones.count() + 1,
            contenido=self.justificacion,
            autor=self.solicitante,
        )
        from comun.models import Notificacion
        if self.solicitante:
            Notificacion.enviar(
                self.solicitante,
                "Solicitud de materia aprobada",
                f"Su solicitud sobre {materia} fue aprobada y publicada en el catálogo.",
            )
