# =====================================================================
# App analítica: predicción de demanda y priorización de inversión
# (Cap. 6 del documento de arquitectura · RF-51 a RF-56)
#
# score = (I × U) / (E + ε)
#   I = impacto (crítico, alto, medio, bajo)
#   U = urgencia (docente, administrativa, infraestructura, tecnológica)
#   E = esfuerzo estimado (horas/hombre normalizadas)
#   ε = 0.5 (evita la división por cero)
# =====================================================================
from django.db import models

EPSILON = 0.5

FACTOR_IMPACTO = {"CRITICO": 4.0, "ALTO": 3.0, "MEDIO": 2.0, "BAJO": 1.0}
FACTOR_URGENCIA = {"DOCENTE": 1.5, "ADMINISTRATIVA": 1.3,
                   "INFRAESTRUCTURA": 1.2, "TECNOLOGICA": 1.1}


class NecesidadDetectada(models.Model):
    """Necesidad capturada de los datos operativos (RF-51, RF-52)."""

    class Impacto(models.TextChoices):
        CRITICO = "CRITICO", "Crítico"
        ALTO = "ALTO", "Alto"
        MEDIO = "MEDIO", "Medio"
        BAJO = "BAJO", "Bajo"

    class Urgencia(models.TextChoices):
        DOCENTE = "DOCENTE", "Docente"
        ADMINISTRATIVA = "ADMINISTRATIVA", "Administrativa"
        INFRAESTRUCTURA = "INFRAESTRUCTURA", "Infraestructura"
        TECNOLOGICA = "TECNOLOGICA", "Tecnológica"

    class Origen(models.TextChoices):
        QUEJAS = "QUEJAS", "Quejas recurrentes"
        CUPOS = "CUPOS", "Demanda insatisfecha de cupos"
        INASISTENCIA = "INASISTENCIA", "Inasistencia elevada"
        EVALUACION = "EVALUACION", "Evaluación docente baja"
        MANUAL = "MANUAL", "Registro manual"

    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    origen = models.CharField(max_length=12, choices=Origen.choices,
                              default=Origen.MANUAL)
    impacto = models.CharField(max_length=8, choices=Impacto.choices,
                               default=Impacto.MEDIO)
    urgencia = models.CharField(max_length=15, choices=Urgencia.choices,
                                default=Urgencia.DOCENTE)
    esfuerzo = models.FloatField("esfuerzo estimado (horas)", default=8)
    evidencia = models.JSONField(default=dict, blank=True,
                                 help_text="Métricas de respaldo (RF-52).")
    score = models.FloatField("score calculado", default=0, db_index=True)
    periodo = models.CharField(max_length=10, blank=True, db_index=True)
    creada = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score", "-creada"]
        verbose_name = "necesidad detectada"
        verbose_name_plural = "necesidades detectadas"

    def __str__(self):
        return f"[{self.score:.2f}] {self.titulo}"

    # --------------------- Modelo matemático (Cap. 6) ---------------------
    def calcular_score(self):
        """score = (I × U) / (E + ε), redondeado a 4 decimales."""
        i = FACTOR_IMPACTO.get(self.impacto, 1.0)
        u = FACTOR_URGENCIA.get(self.urgencia, 1.0)
        esfuerzo = self.esfuerzo or 0
        self.score = round((i * u) / (esfuerzo + EPSILON), 4)
        return self.score

    def save(self, *args, **kwargs):
        self.calcular_score()
        super().save(*args, **kwargs)

    @staticmethod
    def clasificar(score):
        """Clasificación por score (RN de priorización del Cap. 6)."""
        if score >= 1.0:
            return "CRITICA"
        if score >= 0.5:
            return "ALTA"
        if score >= 0.25:
            return "MEDIA"
        return "BAJA"

    @property
    def nivel_prioridad(self):
        return self.clasificar(self.score)

    def recomendar(self):
        """Recomendación textual según el score (RF-53)."""
        nivel = self.nivel_prioridad
        if nivel == "CRITICA":
            return "Atender de inmediato: incluya la necesidad en el plan del periodo."
        if nivel == "ALTA":
            return "Programar en el corto plazo con recursos del departamento."
        if nivel == "MEDIA":
            return "Evaluar alternativas de bajo costo y revalidar el próximo periodo."
        return "Monitorear; el esfuerzo supera el beneficio inmediato."


class PrediccionDemanda(models.Model):
    """Predicción de demanda por materia y periodo (RF-54, RF-55)."""

    class Metodo(models.TextChoices):
        PROMEDIO_MOVIL = "MM", "Promedio móvil"
        REGRESION = "REG", "Regresión lineal simple"
        HISTORICO = "HIST", "Histórico simple"

    materia = models.ForeignKey("materias.Materia", on_delete=models.CASCADE,
                                related_name="predicciones")
    periodo_objetivo = models.CharField(max_length=10, db_index=True)
    demanda_estimada = models.FloatField(default=0)
    demanda_real = models.PositiveIntegerField(null=True, blank=True)
    cupo_sugerido = models.PositiveSmallIntegerField(default=0)
    metodo = models.CharField(max_length=4, choices=Metodo.choices,
                              default=Metodo.PROMEDIO_MOVIL)
    confianza = models.FloatField("confianza (0-1)", default=0)
    detalle = models.JSONField(default=dict, blank=True)
    generada = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ("materia", "periodo_objetivo")
        ordering = ["-demanda_estimada"]
        verbose_name = "predicción de demanda"
        verbose_name_plural = "predicciones de demanda"

    def __str__(self):
        return f"{self.materia} · {self.periodo_objetivo} → {self.demanda_estimada:.0f}"

    def error_absoluto(self):
        """RF-55: error de la predicción frente a la demanda real observada."""
        if not self.demanda_real:
            return None
        return round(abs(self.demanda_estimada - self.demanda_real), 2)

