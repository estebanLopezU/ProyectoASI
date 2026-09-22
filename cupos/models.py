# =====================================================================
# App cupos: ofertas por periodo, solicitudes y lista de espera
# RF-05 a RF-10 · Reglas RN-01 (prerrequisitos), RN-02 (cupo máximo),
# RN-03 (conflicto de horario) y RN-04 (priorización)
# =====================================================================
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class OfertaCupo(models.Model):
    """Grupo (sección/NRC) de una materia en un periodo académico.

    Una misma materia puede tener varios grupos en el mismo periodo; cada
    grupo tiene su propio docente responsable, horario («franja») y cupos.
    El estudiante se inscribe a un grupo concreto, no a la materia.
    """

    materia = models.ForeignKey("materias.Materia", on_delete=models.CASCADE,
                                related_name="ofertas")
    periodo = models.CharField("periodo académico", max_length=10, db_index=True)
    grupo = models.CharField("grupo / sección", max_length=10, default="G1",
                             help_text="Identificador del grupo (ej. G1, G2, NRC).")
    docente = models.ForeignKey("usuario.Usuario", null=True, blank=True,
                                on_delete=models.SET_NULL,
                                related_name="grupos_dictados",
                                limit_choices_to={"rol": "DOCENTE"},
                                verbose_name="docente del grupo")
    cupo_maximo = models.PositiveSmallIntegerField("cupo máximo")
    inscritos = models.PositiveSmallIntegerField("inscritos", default=0)
    dia = models.PositiveSmallIntegerField("día (1=lun ... 7=dom)", default=1)
    hora_inicio = models.TimeField("hora inicio", default="07:00")
    hora_fin = models.TimeField("hora fin", default="09:00")
    aula = models.CharField("aula / salón", max_length=30, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        unique_together = ("materia", "periodo", "grupo")
        ordering = ["periodo", "materia__codigo", "grupo"]
        verbose_name = "grupo de cupos"
        verbose_name_plural = "grupos de cupos"

    def __str__(self):
        return (f"{self.materia} · {self.periodo} · {self.grupo} "
                f"· {self.cupos_disponibles} disponibles")

    @property
    def etiqueta_grupo(self):
        """Nombre corto del grupo para las tablas."""
        return self.grupo or "G1"

    @property
    def docente_nombre(self):
        """Nombre del docente responsable del grupo."""
        if not self.docente:
            # Respaldo: primer docente activo asignado a la materia
            docente = self.materia.docentes.filter(is_active=True).first()
            return (docente.get_full_name() or docente.username) if docente else ""
        return self.docente.get_full_name() or self.docente.username

    @property
    def cupos_disponibles(self):
        return max(self.cupo_maximo - self.inscritos, 0)

    @property
    def tasa_ocupacion(self):
        return self.inscritos / self.cupo_maximo if self.cupo_maximo else 0

    @property
    def porcentaje_ocupacion(self):
        """Ocupación del grupo como porcentaje entero para barras de progreso."""
        return int(round(self.tasa_ocupacion * 100))

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
    """Cupo confirmado del estudiante en un grupo concreto (matrícula)."""

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
        return (f"{self.estudiante} en {self.oferta.materia} "
                f"[{self.oferta.grupo}] [{self.estado}]")

    # Atajos de grupo -----------------------------------------------
    @property
    def grupo(self):
        return self.oferta.grupo

    @property
    def docente(self):
        return self.oferta.docente

    @property
    def docente_nombre(self):
        return self.oferta.docente_nombre


# =====================================================================
# Preinscripción de asignaturas (RF-05 ampliado · RN-13, RN-14)
# El estudiante registra su intención de cursar un conjunto de materias
# para el próximo periodo, ordenadas por preferencia. El sistema calcula
# la probabilidad de apertura/otorgamiento a partir de la demanda
# agregada de todos los estudiantes, las franjas horarias compatibles y
# los docentes activos asignados a cada materia.
# =====================================================================
class Preinscripcion(models.Model):
    """Intención de cursar una materia en el próximo periodo (RN-13)."""

    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        ENVIADA = "ENVIADA", "Enviada"
        CONFIRMADA = "CONFIRMADA", "Confirmada en oferta"
        RECHAZADA = "RECHAZADA", "Rechazada"

    MINIMO_MATERIAS = 5  # RN-13: mínimo de materias por preinscripción

    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="preinscripciones")
    materia = models.ForeignKey("materias.Materia", on_delete=models.CASCADE,
                                related_name="preinscripciones")
    periodo_objetivo = models.CharField("periodo objetivo", max_length=10, db_index=True)
    prioridad = models.PositiveSmallIntegerField("orden de preferencia", default=1)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.ENVIADA)
    probabilidad = models.FloatField("probabilidad de asignación (0-1)", default=0)
    demanda_estimada = models.FloatField("demanda estimada del periodo", default=0)
    franja_sugerida = models.CharField("franja sugerida", max_length=60, blank=True)
    docentes_activos = models.PositiveSmallIntegerField("docentes activos", default=0)
    grupo = models.ForeignKey("cupos.OfertaCupo", null=True, blank=True,
                              on_delete=models.SET_NULL,
                              related_name="preinscripciones_grupo",
                              verbose_name="grupo preferido")
    observacion = models.CharField(max_length=200, blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("estudiante", "materia", "periodo_objetivo")
        ordering = ["periodo_objetivo", "prioridad"]
        verbose_name = "preinscripción"
        verbose_name_plural = "preinscripciones"

    def __str__(self):
        return f"{self.estudiante} → {self.materia} (P{self.prioridad})"

    @property
    def porcentaje(self):
        """Probabilidad expresada en porcentaje entero para la interfaz."""
        return int(round(self.probabilidad * 100))

    @property
    def nivel_riesgo(self):
        """Clasificación cualitativa de la probabilidad."""
        if self.probabilidad >= 0.75:
            return "ALTA"
        if self.probabilidad >= 0.5:
            return "MEDIA"
        if self.probabilidad >= 0.3:
            return "BAJA"
        return "CRITICA"

    @property
    def color_badge(self):
        """Clase Bootstrap asociada al nivel de probabilidad."""
        return {"ALTA": "success", "MEDIA": "info",
                "BAJA": "warning", "CRITICA": "danger"}[self.nivel_riesgo]


class PreferenciaPreinscripcion(models.Model):
    """Franjas horarias preferidas por el estudiante (RN-14).

    Cada preferencia describe un día y una franja en la que el estudiante
    puede cursar clases; el motor sugiere horarios que no choquen entre sí
    ni con sus inscripciones activas.
    """

    class Franja(models.TextChoices):
        MANANA = "MANANA", "Mañana (07:00-12:00)"
        TARDE = "TARDE", "Tarde (12:00-18:00)"
        NOCHE = "NOCHE", "Noche (18:00-22:00)"

    DIAS = ((1, "Lunes"), (2, "Martes"), (3, "Miércoles"),
            (4, "Jueves"), (5, "Viernes"), (6, "Sábado"))

    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="preferencias_horario")
    periodo_objetivo = models.CharField("periodo objetivo", max_length=10, db_index=True)
    dia = models.PositiveSmallIntegerField("día (1=lun ... 6=sáb)", choices=DIAS, default=1)
    franja = models.CharField(max_length=6, choices=Franja.choices, default=Franja.MANANA)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("estudiante", "periodo_objetivo", "dia", "franja")
        ordering = ["dia", "franja"]
        verbose_name = "preferencia de horario"
        verbose_name_plural = "preferencias de horario"

    def __str__(self):
        return f"{self.estudiante} · {self.get_dia_display()} {self.get_franja_display()}"

