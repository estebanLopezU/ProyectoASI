# =====================================================================
# App quejas: casos con trazabilidad y escalamiento (RF-35 a RF-42)
# Reglas RN-09 (confidencialidad), RN-10 (escalamiento 3 días),
# RN-11 (soluciones rápidas) y RN-12 (cierre con confirmación).
# =====================================================================
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class CategoriaQueja(models.Model):
    """Categorías con respuesta rápida predefinida (RN-11 / RF-42)."""

    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)
    solucion_rapida = models.TextField(
        "solución rápida", blank=True,
        help_text="Respuesta sugerida que resuelve el caso sin escalamiento (RN-11).",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "categoría de queja"
        verbose_name_plural = "categorías de queja"

    def __str__(self):
        return self.nombre


class Queja(models.Model):
    """Caso de queja o reclamo con flujo y trazabilidad (RF-35 a RF-42)."""

    class Estado(models.TextChoices):
        ABIERTO = "ABIERTO", "Abierto"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        ESCALADO = "ESCALADO", "Escalado al departamento"
        RESUELTO = "RESUELTO", "Resuelto"
        CERRADO = "CERRADO", "Cerrado por el usuario"

    class Prioridad(models.TextChoices):
        BAJA = "BAJA", "Baja"
        MEDIA = "MEDIA", "Media"
        ALTA = "ALTA", "Alta"

    consecutivo = models.CharField(max_length=20, unique=True, blank=True, db_index=True)
    radicada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="quejas")
    anonima = models.BooleanField(default=False,
                                  help_text="La identidad se oculta al gestor (RN-09).")
    categoria = models.ForeignKey(CategoriaQueja, on_delete=models.PROTECT,
                                  related_name="quejas")
    materia = models.ForeignKey("materias.Materia", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="quejas")
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField()
    evidencia = models.FileField(upload_to="quejas/", blank=True, null=True)
    estado = models.CharField(max_length=10, choices=Estado.choices,
                              default=Estado.ABIERTO)
    prioridad = models.CharField(max_length=5, choices=Prioridad.choices,
                                 default=Prioridad.MEDIA)
    gestor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="quejas_gestionadas")
    solucion = models.TextField(blank=True)
    creada = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizada = models.DateTimeField(auto_now=True)
    escalada = models.DateTimeField(null=True, blank=True)
    resuelta = models.DateTimeField(null=True, blank=True)
    confirmada_por_usuario = models.BooleanField(default=False)
    satisfaccion = models.PositiveSmallIntegerField(null=True, blank=True,
                                                    help_text="1 a 5 (RF-42).")

    class Meta:
        ordering = ["-creada"]
        verbose_name = "queja"
        verbose_name_plural = "quejas"

    def __str__(self):
        return f"{self.consecutivo} · {self.asunto} [{self.get_estado_display()}]"

    # ----------------------- Reglas de negocio -----------------------
    def save(self, *args, **kwargs):
        if not self.consecutivo:
            self.consecutivo = self._nuevo_consecutivo()
        super().save(*args, **kwargs)

    def _nuevo_consecutivo(self):
        anio = timezone.localdate().year
        total = Queja.objects.filter(creada__year=anio).count() + 1
        return f"Q-{anio}-{total:05d}"

    def horas_sin_gestion(self):
        """Horas desde la radicación o la última gestión (RN-10)."""
        base = self.actualizada if self.estado != self.Estado.ABIERTO else self.creada
        return (timezone.now() - base).total_seconds() / 3600

    def requiere_escalamiento(self):
        """RN-10: sin gestión durante SGDIC_DIAS_ESCALAMIENTO días."""
        if self.estado in (self.Estado.RESUELTO, self.Estado.CERRADO, self.Estado.ESCALADO):
            return False
        limite = settings.SGDIC_DIAS_ESCALAMIENTO * 24
        return self.horas_sin_gestion() >= limite

    @transaction.atomic
    def escalar(self, motivo=""):
        """RF-38/RN-10: escala automáticamente al departamento."""
        if not self.requiere_escalamiento() and self.estado != self.Estado.ABIERTO:
            return False
        from comun.models import Notificacion
        from usuario.models import Usuario

        self.estado = self.Estado.ESCALADO
        self.escalada = timezone.now()
        self.actualizada = timezone.now()
        self.save()
        detalle = motivo or (
            f"Sin gestión en {settings.SGDIC_DIAS_ESCALAMIENTO} días "
            f"(RN-10). Caso {self.consecutivo}."
        )
        for gestor in Usuario.objects.filter(rol__in=("DEPARTAMENTO", "SECRETARIA")):
            Notificacion.enviar(gestor, "Queja escalada al departamento", detalle,
                                url="/quejas/",
                                nivel=Notificacion.Nivel.CRITICA)
        return True

    def puede_ser_anonima(self):
        """RN-09: nunca se revela la identidad del denunciante anónimo."""
        return self.anonima

    @property
    def identidad_visible(self):
        return "Anónimo" if self.anonima else str(self.radicada_por)

    @transaction.atomic
    def asignar(self, gestor, comentario=""):
        """RF-37: asignación del caso a un gestor."""
        self.gestor = gestor
        self.estado = self.Estado.EN_PROCESO
        self.actualizada = timezone.now()
        self.save()
        self.seguimientos.create(
            autor=gestor, tipo=Seguimiento.Tipo.ASIGNACION,
            detalle=comentario or f"Caso asignado a {gestor}.",
        )
        from comun.models import Notificacion
        Notificacion.enviar(
            self.radicada_por, "Su queja fue asignada",
            f"Caso {self.consecutivo} en proceso con {gestor}.",
            url=f"/quejas/{self.pk}/",
        )
        return self

    def aplicar_solucion_rapida(self, gestor, detalle=""):
        """RF-42/RN-11: respuesta inmediata desde la categoría."""
        if not self.categoria.solucion_rapida and not detalle:
            return False
        self.resolver(gestor, self.categoria.solucion_rapida or detalle, rapida=True)
        return True

    @transaction.atomic
    def seguimiento(self, autor, detalle, estado=None, tipo=None):
        """Registra avance del caso (RF-40)."""
        registro = self.seguimientos.create(
            autor=autor, detalle=detalle,
            tipo=tipo or Seguimiento.Tipo.AVANCE,
        )
        if estado:
            self.estado = estado
        self.actualizada = timezone.now()
        self.save()
        return registro

    @transaction.atomic
    def resolver(self, gestor, solucion, rapida=False):
        """RF-39: marca el caso como resuelto y notifica (RN-12)."""
        from comun.models import Notificacion

        self.gestor = gestor or self.gestor
        self.solucion = solucion
        self.estado = self.Estado.RESUELTO
        self.resuelta = timezone.now()
        self.actualizada = timezone.now()
        self.save()
        self.seguimientos.create(
            autor=gestor, tipo=Seguimiento.Tipo.SOLUCION,
            detalle=solucion + (" (solución rápida, RN-11)" if rapida else ""),
        )
        Notificacion.enviar(
            self.radicada_por, "Su queja fue resuelta",
            f"Caso {self.consecutivo}: {solucion}. "
            "Confirme el cierre o reabra el caso si persiste el problema.",
            url=f"/quejas/{self.pk}/",
        )
        return self

    @transaction.atomic
    def confirmar_cierre(self, satisfaccion=None):
        """RN-12: el usuario confirma el cierre y califica la atención."""
        self.confirmada_por_usuario = True
        self.satisfaccion = satisfaccion or self.satisfaccion
        self.estado = self.Estado.CERRADO
        self.actualizada = timezone.now()
        self.save()
        self.seguimientos.create(
            autor=self.radicada_por, tipo=Seguimiento.Tipo.CIERRE,
            detalle="El usuario confirmó la solución y cerró el caso.",
        )
        return self

    @transaction.atomic
    def reabrir(self, comentario=""):
        """RN-12: el usuario reabre si el problema persiste."""
        self.confirmada_por_usuario = False
        self.estado = self.Estado.EN_PROCESO if self.gestor else self.Estado.ABIERTO
        self.actualizada = timezone.now()
        self.save()
        self.seguimientos.create(
            autor=self.radicada_por, tipo=Seguimiento.Tipo.REAPERTURA,
            detalle=comentario or "El usuario reabrió el caso: el problema persiste.",
        )
        return self


class Seguimiento(models.Model):
    """Bitácora de trazabilidad del caso (RF-40)."""

    class Tipo(models.TextChoices):
        ASIGNACION = "ASIGNACION", "Asignación"
        AVANCE = "AVANCE", "Avance"
        SOLUCION = "SOLUCION", "Solución"
        REAPERTURA = "REAPERTURA", "Reapertura"
        CIERRE = "CIERRE", "Cierre"
        ESCALAMIENTO = "ESCALAMIENTO", "Escalamiento"

    queja = models.ForeignKey(Queja, on_delete=models.CASCADE, related_name="seguimientos")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="seguimientos_queja")
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.AVANCE)
    detalle = models.TextField()
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["creado"]
        verbose_name = "seguimiento"
        verbose_name_plural = "seguimientos"

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.queja.consecutivo}"

