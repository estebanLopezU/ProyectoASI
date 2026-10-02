# =====================================================================
# App investigacion: grupos de investigación y semilleros.
# Publican: DOCENTE, SECRETARIA, DEPARTAMENTO (ADMIN siempre pasa).
# Ven: todos los roles.
# Se pueden inscribir: solo DOCENTE y ESTUDIANTE, y la inscripción
# requiere la aprobación del docente coordinador del grupo.
# =====================================================================
from django.conf import settings
from django.db import models
from django.utils import timezone

# Quién publica grupos (reutilizado por vistas, forms y plantillas).
ROLES_PUBLICAN = ("DOCENTE", "SECRETARIA", "DEPARTAMENTO", "ADMIN")

# Quién puede MENEAR una inscripción: solo estos dos roles.
ROLES_INSCRIBEN = ("ESTUDIANTE", "DOCENTE")


class Grupo(models.Model):
    """Grupo de investigación o semillero de investigación.

    `cupo` vacío significa sin límite. La inscripción nunca es automática:
    el interesado solicita y el docente coordinador acepta o rechaza
    (ver `Inscripcion`).
    """

    class Tipo(models.TextChoices):
        SEMILLERO = "SEMILLERO", "Semillero de investigación"
        GRUPO = "GRUPO", "Grupo de investigación"

    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=12, choices=Tipo.choices,
                            default=Tipo.SEMILLERO, db_index=True)
    descripcion = models.TextField(
        blank=True,
        help_text="Objetivos, líneas de trabajo y forma de participación.",
    )
    linea = models.CharField(
        "línea de investigación", max_length=150, blank=True,
        help_text="Ej.: Inteligencia Artificial, Redes, Software.",
    )
    coordinador = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="grupos_coordinados",
        help_text="Docente que aprueba o rechaza las solicitudes.",
    )
    cupo = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Máximo de miembros. Vacío = sin límite.",
    )
    activo = models.BooleanField(
        default=True, db_index=True,
        help_text="Desactívalo para dejar de recibir solicitudes sin borrar el grupo.",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="grupos_creados",
    )
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-creado", "-pk"]
        verbose_name = "grupo de investigación"
        verbose_name_plural = "grupos de investigación"

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

    # ---- Integrantes --------------------------------------------------
    @property
    def miembros_count(self):
        return self.inscripciones.filter(estado=Inscripcion.Estado.ACEPTADA).count()

    @property
    def pendientes_count(self):
        """Solicitudes esperando respuesta del coordinador."""
        return self.inscripciones.filter(estado=Inscripcion.Estado.PENDIENTE).count()

    @property
    def lleno(self):
        if self.cupo is None:
            return False
        return self.miembros_count >= self.cupo

    @property
    def vacantes(self):
        if self.cupo is None:
            return None
        return max(self.cupo - self.miembros_count, 0)

    # ---- Reglas de acceso --------------------------------------------
    @staticmethod
    def activos():
        return Grupo.objects.filter(activo=True)

    def es_coordinador(self, usuario):
        """Solo el coordinador (o un ADMIN) responde solicitudes."""
        if not usuario or not usuario.is_authenticated:
            return False
        if self.coordinador_id and self.coordinador_id == usuario.pk:
            return True
        return bool(getattr(usuario, "rol", None) == "ADMIN")

    def puede_solicitar(self, usuario):
        """¿Este usuario puede enviar una solicitud de inscripción?"""
        if getattr(usuario, "rol", None) not in ROLES_INSCRIBEN:
            return False
        if not self.activo or self.lleno:
            return False
        if self.coordinador_id and self.coordinador_id == usuario.pk:
            return False  # el coordinador ya está dentro por definición
        return not self.inscripciones.filter(
            usuario=usuario,
            estado__in=(Inscripcion.Estado.PENDIENTE, Inscripcion.Estado.ACEPTADA),
        ).exists()

class Inscripcion(models.Model):
    """Solicitud de ingreso a un grupo (con aprobación del coordinador).

    Flujo: PENDIENTE -> ACEPTADA | RECHAZADA. El interesado puede cancelar
    su propia solicitud mientras siga pendiente (CANCELADA).
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACEPTADA = "ACEPTADA", "Aceptada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        CANCELADA = "CANCELADA", "Cancelada por el usuario"

    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE,
                              related_name="inscripciones")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="inscripciones_grupo",
    )
    estado = models.CharField(max_length=10, choices=Estado.choices,
                              default=Estado.PENDIENTE, db_index=True)
    respuesta = models.TextField(
        blank=True, help_text="Motivo o comentario para el coordinador.",
    )
    creada = models.DateTimeField(auto_now_add=True, db_index=True)
    respondida = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creada", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["grupo", "usuario"],
                name="uniq_inscripcion_grupo_usuario",
            ),
        ]
        verbose_name = "inscripción a grupo"
        verbose_name_plural = "inscripciones a grupos"

    def __str__(self):
        return f"{self.usuario} → {self.grupo} ({self.get_estado_display()})"

    @property
    def es_pendiente(self):
        return self.estado == self.Estado.PENDIENTE

    def aceptar(self):
        """El coordinador acepta: el usuario pasa a ser miembro."""
        from comun.models import Notificacion

        self.estado = self.Estado.ACEPTADA
        self.respondida = timezone.now()
        self.save(update_fields=["estado", "respondida"])
        Notificacion.enviar(
            self.usuario,
            f"Tu solicitud a {self.grupo.nombre} fue aprobada",
            "Ya eres miembro del grupo. Ponte en contacto con el coordinador "
            "para definir tu participación.",
            url="/investigacion/",
        )
        return self

    def rechazar(self, motivo=""):
        """El coordinador rechaza la solicitud."""
        from comun.models import Notificacion

        self.estado = self.Estado.RECHAZADA
        self.respuesta = motivo or self.respuesta
        self.respondida = timezone.now()
        self.save(update_fields=["estado", "respuesta", "respondida"])
        Notificacion.enviar(
            self.usuario,
            f"Tu solicitud a {self.grupo.nombre} fue rechazada",
            motivo or "El coordinador no pudo incluirte por ahora.",
            url="/investigacion/",
        )
        return self
