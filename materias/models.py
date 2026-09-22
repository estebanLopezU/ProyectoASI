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
    semestre = models.PositiveSmallIntegerField(
        "semestre del plan", default=1,
        help_text="Semestre (1-10) en que se cursa según la malla curricular.")
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


class MallaCurricular(models.Model):
    """Estado de una materia dentro de la malla de un estudiante.

    Permite al administrativo colocar la materia en un semestre concreto del
    plan y fijar su estado (pendiente, en curso, vista). Cuando ``estado`` es
    ``None`` el sistema deriva el estado automáticamente a partir de las
    inscripciones del estudiante (APROBADA → vista, ACTIVA → en curso).
    """

    class Estado(models.TextChoices):
        SIN_ESTADO = "", "Automático (derivado de inscripciones)"
        PENDIENTE = "PENDIENTE", "Pendiente (sin ver)"
        EN_CURSO = "EN_CURSO", "En curso (viendo)"
        VISTA = "VISTA", "Vista (ya cursada)"

    estudiante = models.ForeignKey(
        "usuario.Usuario", on_delete=models.CASCADE,
        related_name="malla_curricular",
        limit_choices_to={"rol": "ESTUDIANTE"},
        verbose_name="estudiante",
    )
    materia = models.ForeignKey(
        Materia, on_delete=models.CASCADE,
        related_name="malla_curricular",
        verbose_name="materia",
    )
    semestre = models.PositiveSmallIntegerField(
        "semestre del plan", default=1,
        help_text="Semestre (1-10) en que el estudiante cursa esta materia.")
    estado = models.CharField(
        "estado", max_length=10, choices=Estado.choices,
        blank=True, default=Estado.SIN_ESTADO,
        help_text="Vacío = derivado de las inscripciones del estudiante.")
    observacion = models.CharField(
        "observación", max_length=200, blank=True)
    actualizado_por = models.ForeignKey(
        "usuario.Usuario", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="malla_editada",
        verbose_name="última edición por",
    )
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("estudiante", "materia")
        ordering = ["semestre", "materia__codigo"]
        verbose_name = "malla curricular"
        verbose_name_plural = "mallas curriculares"

    def __str__(self):
        return (f"{self.estudiante} · {self.materia} · sem {self.semestre} "
                f"[{self.get_estado_display()}]")

    @property
    def estado_derivado(self):
        """Estado calculado a partir de las inscripciones del estudiante."""
        from cupos.models import Inscripcion

        estados = set(
            self.estudiante.inscripciones.filter(
                oferta__materia=self.materia
            ).values_list("estado", flat=True)
        )
        if "APROBADA" in estados:
            return self.Estado.VISTA
        if "ACTIVA" in estados:
            return self.Estado.EN_CURSO
        # Complemento: preinscripción activa = en curso previsto
        if self.estudiante.preinscripciones.filter(
            materia=self.materia
        ).exists():
            return self.Estado.EN_CURSO
        return self.Estado.PENDIENTE

    @property
    def estado_efectivo(self):
        """Estado manual si existe; si no, el derivado."""
        return self.estado or self.estado_derivado

    @property
    def etiqueta_corta(self):
        """Etiqueta corta para las tarjetas de la malla."""
        return {
            self.Estado.VISTA: "Vista",
            self.Estado.EN_CURSO: "Cursando",
            self.Estado.PENDIENTE: "Sin ver",
        }.get(self.estado_efectivo, "Sin ver")

    @property
    def color(self):
        """Clase CSS del semáforo (verde/amarillo/rojo)."""
        return {
            self.Estado.VISTA: "verde",
            self.Estado.EN_CURSO: "amarillo",
            self.Estado.PENDIENTE: "rojo",
        }.get(self.estado_efectivo, "rojo")

    @property
    def etiqueta_estado(self):
        """Etiqueta legible del estado efectivo (verde/amarillo/rojo)."""
        return {
            self.Estado.VISTA: "Vista (ya cursada)",
            self.Estado.EN_CURSO: "En curso (viendo)",
            self.Estado.PENDIENTE: "Pendiente (sin ver)",
        }.get(self.estado_efectivo, "Pendiente (sin ver)")
