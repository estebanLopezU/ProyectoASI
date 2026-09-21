# =====================================================================
# Modelo común: auditoría (RNF-09), notificaciones y helpers de roles
# =====================================================================
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

ROLES = [
    ("ESTUDIANTE", "Estudiante"),
    ("DOCENTE", "Docente"),
    ("SECRETARIA", "Secretaría"),
    ("DEPARTAMENTO", "Departamento"),
    ("ADMIN", "Administrador"),
]


class AuditoriaLog(models.Model):
    """Registro inmutable de operaciones críticas (RF-04 / RNF-09)."""

    usuario = models.ForeignKey(
        "usuario.Usuario", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="registros_auditoria",
    )
    accion = models.CharField(max_length=100)
    objeto_tipo = models.CharField(max_length=100)
    objeto_id = models.CharField(max_length=100, blank=True)
    detalle = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} · {self.accion} · {self.objeto_tipo}#{self.objeto_id}"

    @staticmethod
    def registrar(request, accion, objeto, detalle=""):
        Usuario = get_user_model()
        return AuditoriaLog.objects.create(
            usuario=getattr(request, "user", None)
            if getattr(request, "user", None) and request.user.is_authenticated
            else None,
            accion=accion,
            objeto_tipo=objeto.__class__.__name__,
            objeto_id=str(getattr(objeto, "pk", "")),
            detalle=detalle,
        )


class Notificacion(models.Model):
    """Notificación in-app (RF-08, RF-22, RF-39) con envío de correo opcional."""

    class Nivel(models.TextChoices):
        INFO = "INFO", "Informativa"
        ADVERTENCIA = "WARN", "Advertencia"
        CRITICA = "CRIT", "Crítica"

    destinatario = models.ForeignKey(
        "usuario.Usuario", on_delete=models.CASCADE, related_name="notificaciones"
    )
    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    url = models.CharField(max_length=300, blank=True)
    nivel = models.CharField(max_length=4, choices=Nivel.choices, default=Nivel.INFO)
    leida = models.BooleanField(default=False, db_index=True)
    creada = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-creada"]
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self):
        return f"[{self.nivel}] {self.titulo} → {self.destinatario}"

    @staticmethod
    def enviar(destinatario, titulo, cuerpo, url="", nivel=Nivel.INFO, correo=True):
        notif = Notificacion.objects.create(
            destinatario=destinatario, titulo=titulo, cuerpo=cuerpo,
            url=url or "", nivel=nivel,
        )
        if correo and getattr(destinatario, "email", None):
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                f"[ASI] {titulo}",
                cuerpo,
                settings.DEFAULT_FROM_EMAIL,
                [destinatario.email],
                fail_silently=True,
            )
        return notif


def usuario_de(request):
    """Devuelve el Usuario autenticado o None."""
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return user
    return None


def hoy():
    return timezone.localdate()


def now():
    return timezone.now()
