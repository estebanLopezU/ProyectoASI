# =====================================================================
# App evaluaciones: registro de faltas (RF-21 a RF-26) y evaluación
# docente anónima (RF-27 a RF-34). Reglas RN-05, RN-06, RN-07, RN-08.
# =====================================================================
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class Sesion(models.Model):
    """Sesión de clase de una oferta, base para registrar asistencia."""

    oferta = models.ForeignKey("cupos.OfertaCupo", on_delete=models.CASCADE,
                               related_name="sesiones")
    fecha = models.DateField(db_index=True)
    tema = models.CharField(max_length=150, blank=True)
    registrada = models.BooleanField(default=False)

    class Meta:
        unique_together = ("oferta", "fecha")
        ordering = ["-fecha"]
        verbose_name = "sesión de clase"
        verbose_name_plural = "sesiones de clase"

    def __str__(self):
        return f"{self.oferta.materia} · {self.fecha}"


class Falta(models.Model):
    """Inasistencia de un estudiante (RF-21, RN-07)."""

    class Estado(models.TextChoices):
        REGISTRADA = "REGISTRADA", "Registrada"
        JUSTIFICADA = "JUSTIFICADA", "Justificada"
        RECHAZADA = "RECHAZADA", "Justificación rechazada"

    sesion = models.ForeignKey(Sesion, on_delete=models.CASCADE, related_name="faltas")
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="faltas")
    motivo = models.CharField(max_length=200, blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices,
                              default=Estado.REGISTRADA)
    evidencia = models.FileField("evidencia", upload_to="justificaciones/", blank=True, null=True)
    comentario_justificacion = models.TextField(blank=True)
    registrada = models.DateTimeField(auto_now_add=True, db_index=True)
    notificada = models.BooleanField(default=False)

    class Meta:
        unique_together = ("sesion", "estudiante")
        ordering = ["-sesion__fecha"]
        verbose_name = "falta"
        verbose_name_plural = "faltas"

    def __str__(self):
        return f"Falta {self.estudiante} · {self.sesion}"

    @property
    def materia(self):
        return self.sesion.oferta.materia

    def notificar(self):
        """RF-22/RN-07: notifica al estudiante el mismo día del registro."""
        from comun.models import Notificacion

        if self.notificada:
            return None
        notif = Notificacion.enviar(
            self.estudiante,
            "Registro de falta",
            f"Se registró su inasistencia en {self.materia} del {self.sesion.fecha}."
            + (f" Motivo: {self.motivo}" if self.motivo else ""),
            url="/evaluaciones/faltas/",
            nivel=Notificacion.Nivel.ADVERTENCIA,
        )
        self.notificada = True
        self.save(update_fields=["notificada"])
        return notif

    def justificar(self, comentario="", evidencia=None):
        """RF-23: el estudiante adjunta justificación con evidencia."""
        self.comentario_justificacion = comentario
        if evidencia:
            self.evidencia = evidencia
        self.save(update_fields=["comentario_justificacion", "evidencia"])
        docente = self.sesion.oferta.materia.docentes.first()
        if docente:
            from comun.models import Notificacion
            Notificacion.enviar(
                docente,
                "Justificación pendiente de revisión",
                f"{self.estudiante} justificó la falta del {self.sesion.fecha} en {self.materia}.",
                url="/evaluaciones/faltas/revisar/",
            )

    @transaction.atomic
    def revisar(self, aprobada, comentario=""):
        """RF-24: el docente aprueba o rechaza la justificación."""
        self.estado = self.Estado.JUSTIFICADA if aprobada else self.Estado.RECHAZADA
        self.comentario_justificacion = comentario or self.comentario_justificacion
        self.save(update_fields=["estado", "comentario_justificacion"])
        from comun.models import Notificacion
        Notificacion.enviar(
            self.estudiante,
            "Justificación " + ("aprobada" if aprobada else "rechazada"),
            f"Falta del {self.sesion.fecha} en {self.materia}: {self.get_estado_display()}.",
        )



class ResumenInasistencia(models.Model):
    """Porcentaje acumulado por estudiante/materia (RF-25, RN-08)."""

    class Riesgo(models.TextChoices):
        OK = "OK", "Sin riesgo"
        ADVERTENCIA = "WARN", "Advertencia"
        CRITICO = "CRIT", "Riesgo crítico"

    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="resumenes_inasistencia")
    oferta = models.ForeignKey("cupos.OfertaCupo", on_delete=models.CASCADE,
                               related_name="resumenes_inasistencia")
    total_sesiones = models.PositiveIntegerField(default=0)
    faltas = models.PositiveIntegerField(default=0)
    porcentaje = models.FloatField(default=0)
    riesgo = models.CharField(max_length=4, choices=Riesgo.choices, default=Riesgo.OK)
    alerta_enviada = models.BooleanField(default=False)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("estudiante", "oferta")
        verbose_name = "resumen de inasistencia"
        verbose_name_plural = "resúmenes de inasistencia"

    def __str__(self):
        return f"{self.estudiante} · {self.oferta.materia} · {self.porcentaje:.1f}%"

    def calcular(self):
        """RF-25: recalcula el porcentaje acumulado y el nivel de riesgo."""
        total = self.oferta.sesiones.count()
        faltas = self.oferta.faltas_efectivas(self.estudiante)
        self.total_sesiones = total
        self.faltas = faltas
        self.porcentaje = round(faltas * 100.0 / total, 2) if total else 0.0
        umbral = settings.SGDIC_UMBRAL_INASISTENCIA
        if self.porcentaje >= umbral:
            self.riesgo = self.Riesgo.CRITICO
        elif self.porcentaje >= umbral * 0.75:
            self.riesgo = self.Riesgo.ADVERTENCIA
        else:
            self.riesgo = self.Riesgo.OK
        self.save()
        return self.porcentaje

    def alertar_si_corresponde(self):
        """RF-26/RN-08: alerta a estudiante, docente y secretaría."""
        if self.riesgo != self.Riesgo.CRITICO or self.alerta_enviada:
            return False
        from comun.models import Notificacion
        from usuario.models import Usuario

        mensaje = (
            f"{self.estudiante} acumula {self.porcentaje:.1f}% de inasistencia en "
            f"{self.oferta.materia} ({self.faltas}/{self.total_sesiones} sesiones)."
        )
        Notificacion.enviar(self.estudiante, "Alerta de inasistencia", mensaje,
                            url="/evaluaciones/faltas/", nivel=Notificacion.Nivel.CRITICA)
        destinatarios = list(Usuario.objects.filter(rol__in=("SECRETARIA", "DEPARTAMENTO")))
        destinatarios += list(self.oferta.materia.docentes.all())
        for usuario in destinatarios:
            Notificacion.enviar(usuario, "Alerta de inasistencia", mensaje,
                                url="/evaluaciones/inasistencia/",
                                nivel=Notificacion.Nivel.CRITICA)
        self.alerta_enviada = True
        self.save(update_fields=["alerta_enviada"])
        return True



class PeriodoEvaluacion(models.Model):
    """Periodo configurable de evaluación docente (RF-27, RN-06)."""

    nombre = models.CharField(max_length=80)
    fecha_inicio = models.DateField()
    fecha_limite = models.DateField()
    activo = models.BooleanField(default=False)
    bloquear_servicios = models.BooleanField(
        "bloquear servicios hasta evaluar (RF-31)", default=False
    )
    umbral_participacion = models.PositiveSmallIntegerField(
        "umbral mínimo de participación (%)", default=60
    )
    preguntas = models.JSONField(default=list, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_inicio"]
        verbose_name = "periodo de evaluación"
        verbose_name_plural = "periodos de evaluación"

    def __str__(self):
        return f"{self.nombre} ({self.fecha_inicio} – {self.fecha_limite})"

    @property
    def habilitado(self):
        """RF-28/RN-06: habilitado solo dentro de la ventana configurada."""
        return self.activo and self.fecha_inicio <= timezone.localdate() <= self.fecha_limite

    @property
    def vencido(self):
        return timezone.localdate() > self.fecha_limite

    def consolidado_publicable(self):
        """RF-32: publica al vencer el plazo o superar el umbral de participación."""
        invitaciones = self.invitaciones.count()
        if not invitaciones:
            return False
        participacion = self.respuestas.count() * 100.0 / invitaciones
        return self.vencido or participacion >= self.umbral_participacion

    def preguntas_activas(self):
        """Preguntas configuradas por el departamento o las estándar."""
        return self.preguntas or [
            "Claridad en la exposición de los temas",
            "Cumplimiento del programa de la asignatura",
            "Disponibilidad para resolver dudas",
            "Puntualidad y asistencia",
            "Utilidad de los recursos y materiales empleados",
        ]


class InvitacionEvaluacion(models.Model):
    """Invitación estudiante → docente de una materia (RF-29 recordatorios)."""

    periodo = models.ForeignKey(PeriodoEvaluacion, on_delete=models.CASCADE,
                                related_name="invitaciones")
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="invitaciones_evaluacion")
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="invitaciones_recibidas")
    materia = models.ForeignKey("materias.Materia", on_delete=models.CASCADE,
                                related_name="invitaciones_evaluacion")
    completada = models.BooleanField(default=False)
    recordatorio_enviado = models.DateTimeField(null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("periodo", "estudiante", "docente", "materia")
        verbose_name = "invitación de evaluación"
        verbose_name_plural = "invitaciones de evaluación"

    def __str__(self):
        return f"{self.estudiante} evalúa a {self.docente} · {self.materia}"


class RespuestaEvaluacion(models.Model):
    """Respuesta anónima consolidada por docente-materia-periodo (RN-05)."""

    periodo = models.ForeignKey(PeriodoEvaluacion, on_delete=models.CASCADE,
                                related_name="respuestas")
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="evaluaciones_recibidas")
    materia = models.ForeignKey("materias.Materia", on_delete=models.CASCADE,
                                related_name="respuestas_evaluacion")
    puntuacion = models.FloatField("puntuación promedio (1-5)")
    comentario = models.TextField(blank=True)
    respuestas_detalle = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "respuesta de evaluación"
        verbose_name_plural = "respuestas de evaluación"

    def __str__(self):
        return f"{self.docente} · {self.materia} · {self.puntuacion:.2f}"

    @staticmethod
    def puede_publicarse(docente, materia, periodo):
        """RN-05: mínimo de respuestas para mostrar resultados agregados."""
        return (
            RespuestaEvaluacion.objects.filter(
                docente=docente, materia=materia, periodo=periodo
            ).count()
            >= settings.SGDIC_MIN_RESPUESTAS_ANONIMO
        )

