# =====================================================================
# App cupos: ofertas por periodo, solicitudes y lista de espera
# RF-05 a RF-10 · Reglas RN-01 (prerrequisitos), RN-02 (cupo máximo),
# RN-03 (conflicto de horario) y RN-04 (priorización)
# =====================================================================
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class OfertaCupo(models.Model):
    """Oferta de cupos de una materia en un periodo académico."""

    materia = models.ForeignKey("materias.Materia", on_delete=models.CASCADE,
                                related_name="ofertas")
    periodo = models.CharField("periodo académico", max_length=10, db_index=True)
    cupo_maximo = models.PositiveSmallIntegerField("cupo máximo")
    inscritos = models.PositiveSmallIntegerField("inscritos", default=0)
    dia = models.PositiveSmallIntegerField("día (1=lun ... 7=dom)", default=1)
    hora_inicio = models.TimeField("hora inicio", default="07:00")
    hora_fin = models.TimeField("hora fin", default="09:00")
    activa = models.BooleanField(default=True)

    class Meta:
        unique_together = ("materia", "periodo")
        ordering = ["periodo", "materia__codigo"]
        verbose_name = "oferta de cupos"
        verbose_name_plural = "ofertas de cupos"

    def __str__(self):
        return f"{self.materia} · {self.periodo} · {self.cupos_disponibles} disponibles"

    @property
    def cupos_disponibles(self):
        return max(self.cupo_maximo - self.inscritos, 0)

    @property
    def tasa_ocupacion(self):
        return self.inscritos / self.cupo_maximo if self.cupo_maximo else 0

    @property
    def franja(self):
        dias = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
        dia = dias[self.dia - 1] if 1 <= self.dia <= 7 else str(self.dia)
        return f"{dia} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}"

    def solapa_con(self, otra):
        """Detecta conflicto de franja horaria (RN-03)."""
        return (
            self.dia == otra.dia
            and self.hora_inicio < otra.hora_fin
            and otra.hora_inicio < self.hora_fin
        )

    def faltas_efectivas(self, estudiante):
        """Faltas no justificadas del estudiante en esta oferta (RF-25)."""
        from evaluaciones.models import Falta, Sesion

        sesiones = Sesion.objects.filter(oferta=self)
        return Falta.objects.filter(sesion__in=sesiones, estudiante=estudiante).exclude(
            estado=Falta.Estado.JUSTIFICADA
        ).count()

    def siguiente_en_espera(self):
        return self.solicitudes.filter(estado=SolicitudCupo.Estado.EN_ESPERA).order_by(
            "-prioridad", "creada"
        ).first()


class SolicitudCupo(models.Model):
    """Solicitud de cupo de un estudiante (RF-05)."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        EN_ESPERA = "EN_ESPERA", "En lista de espera"

    oferta = models.ForeignKey(OfertaCupo, on_delete=models.CASCADE, related_name="solicitudes")
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="solicitudes_cupo")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    prioridad = models.FloatField("prioridad calculada", default=0)
    justificacion_estado = models.CharField(max_length=200, blank=True)
    creada = models.DateTimeField(auto_now_add=True, db_index=True)
    resuelta = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("oferta", "estudiante")
        ordering = ["-prioridad", "creada"]
        verbose_name = "solicitud de cupo"
        verbose_name_plural = "solicitudes de cupo"

    def __str__(self):
        return f"{self.estudiante} → {self.oferta.materia} ({self.get_estado_display()})"

    # ---------------- Reglas de negocio ----------------
    def _prioridad_total(self):
        """RF-07/RN-04: promedio + avance curricular + antigüedad."""
        base = float(getattr(self.estudiante, "promedio", 0) or 0)
        avance = float(getattr(self.estudiante, "semestre", 0) or 0) / 10.0
        antiguedad = 0.0
        if self.creada:
            antiguedad = (timezone.now() - self.creada).total_seconds() / 86400 / 100
        return round(base + avance + antiguedad, 4)

    @property
    def cumple_prerrequisitos(self):
        """RN-01: exige materias prerrequisito aprobadas."""
        aprobadas = set(
            self.estudiante.inscripciones.filter(
                estado=Inscripcion.Estado.APROBADA
            ).values_list("oferta__materia__codigo", flat=True)
        )
        requeridos = set(
            self.oferta.materia.prerrequisitos.values_list("codigo", flat=True)
        )
        return requeridos.issubset(aprobadas)

    def conflicto_horario(self):
        """RN-03: materia con franja solapada e inscripción activa."""
        activas = Inscripcion.objects.filter(
            estudiante=self.estudiante, estado=Inscripcion.Estado.ACTIVA
        ).select_related("oferta")
        for inscripcion in activas:
            if self.oferta.solapa_con(inscripcion.oferta):
                return inscripcion.oferta.materia
        return None

    @transaction.atomic
    def procesar(self):
        """Valida y resuelve la solicitud (RF-06, RN-01 a RN-04)."""
        if self.estado != self.Estado.PENDIENTE:
            return self.estado
        if not self.cumple_prerrequisitos:
            self.estado = self.Estado.RECHAZADA
            self.justificacion_estado = "No cumple prerrequisitos (RN-01)"
        else:
            conflicto = self.conflicto_horario()
            if conflicto:
                self.estado = self.Estado.RECHAZADA
                self.justificacion_estado = f"Conflicto de horario con {conflicto} (RN-03)"
            elif self.oferta.cupos_disponibles > 0:
                self.estado = self.Estado.APROBADA
                self.justificacion_estado = "Cupo aprobado"
                OfertaCupo.objects.filter(pk=self.oferta.pk).update(
                    inscritos=models.F("inscritos") + 1
                )
                self.oferta.refresh_from_db()
                Inscripcion.objects.get_or_create(
                    estudiante=self.estudiante, oferta=self.oferta,
                    defaults={"estado": Inscripcion.Estado.ACTIVA},
                )
            else:
                self.estado = self.Estado.EN_ESPERA
                self.justificacion_estado = "Sin cupos disponibles (RN-02)"
        self.prioridad = self._prioridad_total()
        self.save()
        from comun.models import Notificacion
        Notificacion.enviar(
            self.estudiante,
            f"Solicitud de cupo {self.get_estado_display().lower()}",
            f"{self.oferta.materia} · {self.oferta.periodo}: {self.justificacion_estado}",
            url="/cupos/",
        )
        return self.estado


class Inscripcion(models.Model):
    """Cupo confirmado del estudiante en una oferta (matrícula)."""

    class Estado(models.TextChoices):
        ACTIVA = "ACTIVA", "Activa"
        APROBADA = "APROBADA", "Materia aprobada"
        CANCELADA = "CANCELADA", "Cancelada"

    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="inscripciones")
    oferta = models.ForeignKey(OfertaCupo, on_delete=models.CASCADE, related_name="inscripciones")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVA)
    confirmada = models.DateTimeField(null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("estudiante", "oferta")
        verbose_name = "inscripción"
        verbose_name_plural = "inscripciones"

    def __str__(self):
        return f"{self.estudiante} en {self.oferta.materia} [{self.estado}]"

