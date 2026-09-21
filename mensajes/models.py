# =====================================================================
# App mensajes: mensajería trazable estudiante-docente con intervención
# de secretaría (RF-16 a RF-20)
# =====================================================================
from django.conf import settings
from django.db import models
from django.urls import reverse


class Hilo(models.Model):
    """Conversación trazable entre estudiante y docente (RF-18)."""

    class Tipo(models.TextChoices):
        ACADEMICO = "ACADEMICO", "Académico"
        ADMINISTRATIVO = "ADMINISTRATIVO", "Administrativo"

    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="hilos_como_estudiante",
                                   limit_choices_to={"rol": "ESTUDIANTE"})
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="hilos_como_docente",
                                limit_choices_to={"rol": "DOCENTE"})
    materia = models.ForeignKey("materias.Materia", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="hilos")
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.ACADEMICO)
    asunto = models.CharField(max_length=150)
    intervenido_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                        on_delete=models.SET_NULL,
                                        related_name="hilos_intervenidos")
    cerrado = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "hilo de mensajería"
        verbose_name_plural = "hilos de mensajería"

    def __str__(self):
        return f"{self.asunto} · {self.estudiante} ↔ {self.docente}"

    def get_absolute_url(self):
        return reverse("mensajes:hilo", args=[self.pk])

    def participante(self, usuario):
        return usuario.pk in (
            self.estudiante_id, self.docente_id,
            self.intervenido_por_id,
        )

    def ultimo_mensaje(self):
        return self.mensajes.order_by("-creado").first()

    def horas_sin_respuesta(self):
        """Horas desde el último mensaje del estudiante sin respuesta (RF-19)."""
        ultimo = self.ultimo_mensaje()
        if not ultimo or ultimo.autor.rol != "ESTUDIANTE":
            return 0
        from django.utils import timezone
        return (timezone.now() - ultimo.creado).total_seconds() / 3600


class Mensaje(models.Model):
    """Mensaje dentro de un hilo con estado enviado/leído (RF-18)."""

    hilo = models.ForeignKey(Hilo, on_delete=models.CASCADE, related_name="mensajes")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="mensajes_enviados")
    contenido = models.TextField()
    leido = models.BooleanField(default=False, db_index=True)
    leido_en = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["creado"]
        verbose_name = "mensaje"
        verbose_name_plural = "mensajes"

    def __str__(self):
        return f"#{self.pk} {self.autor} · {self.creado:%Y-%m-%d %H:%M}"

    def marcar_leido(self):
        if not self.leido:
            from django.utils import timezone
            self.leido = True
            self.leido_en = timezone.now()
            self.save(update_fields=["leido", "leido_en"])
