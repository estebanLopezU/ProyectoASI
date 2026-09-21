# =====================================================================
# App reportes: generación, programación y exportación (RF-43 a RF-50)
# =====================================================================
from django.conf import settings
from django.db import models
from django.utils import timezone


class PlantillaReporte(models.Model):
    """Plantilla parametrizable por tipo de reporte (RF-43, RF-44)."""

    class Tipo(models.TextChoices):
        OCUPACION = "OCUPACION", "Ocupación de cupos"
        INASISTENCIA = "INASISTENCIA", "Inasistencia"
        QUEJAS = "QUEJAS", "Quejas y tiempos de respuesta"
        EVALUACION = "EVALUACION", "Evaluación docente"
        SOLICITUDES = "SOLICITUDES", "Solicitudes de materia"
        MENSAJERIA = "MENSAJERIA", "Mensajería y tiempos de respuesta"
        ACADEMICO = "ACADEMICO", "Resumen académico"

    nombre = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    descripcion = models.TextField(blank=True)
    filtros = models.JSONField(default=dict, blank=True,
                               help_text="Parámetros por defecto del reporte.")
    columnas = models.JSONField(default=list, blank=True,
                                help_text="Columnas visibles en la exportación.")
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "plantilla de reporte"
        verbose_name_plural = "plantillas de reporte"

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"


class ReporteGenerado(models.Model):
    """Instancia generada, lista para descarga (RF-45, RF-46)."""

    class Formato(models.TextChoices):
        PDF = "PDF", "PDF"
        XLSX = "XLSX", "Excel"
        CSV = "CSV", "CSV"

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        LISTO = "LISTO", "Listo"
        ERROR = "ERROR", "Con error"

    plantilla = models.ForeignKey(PlantillaReporte, on_delete=models.CASCADE,
                                  related_name="reportes")
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name="reportes_generados")
    parametros = models.JSONField(default=dict, blank=True)
    formato = models.CharField(max_length=4, choices=Formato.choices,
                               default=Formato.CSV)
    estado = models.CharField(max_length=10, choices=Estado.choices,
                              default=Estado.PENDIENTE)
    archivo = models.FileField(upload_to="reportes/", blank=True, null=True)
    total_registros = models.PositiveIntegerField(default=0)
    contenido = models.TextField(blank=True,
                                 help_text="Caché del contenido generado (CSV).")
    mensaje_error = models.CharField(max_length=300, blank=True)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)
    generado = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "reporte generado"
        verbose_name_plural = "reportes generados"

    def __str__(self):
        return f"{self.plantilla.nombre} · {self.creado:%Y-%m-%d %H:%M}"

    def marcar_listo(self, registros, contenido="", archivo=None):
        self.total_registros = registros
        self.contenido = contenido
        if archivo:
            self.archivo = archivo
        self.estado = self.Estado.LISTO
        self.generado = timezone.now()
        self.save()
        return self


class ProgramacionReporte(models.Model):
    """Envío periódico automático del reporte (RF-48)."""

    class Frecuencia(models.TextChoices):
        DIARIA = "DIARIA", "Diaria"
        SEMANAL = "SEMANAL", "Semanal"
        MENSUAL = "MENSUAL", "Mensual"

    plantilla = models.ForeignKey(PlantillaReporte, on_delete=models.CASCADE,
                                  related_name="programaciones")
    frecuencia = models.CharField(max_length=8, choices=Frecuencia.choices,
                                  default=Frecuencia.SEMANAL)
    destinatarios = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                           related_name="reportes_programados")
    formato = models.CharField(max_length=4, choices=ReporteGenerado.Formato.choices,
                               default=ReporteGenerado.Formato.CSV)
    activa = models.BooleanField(default=True)
    ultima_ejecucion = models.DateTimeField(null=True, blank=True)
    proxima_ejecucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["plantilla__nombre"]
        verbose_name = "programación de reporte"
        verbose_name_plural = "programaciones de reportes"

    def __str__(self):
        return f"{self.plantilla.nombre} · {self.get_frecuencia_display()}"

    def calcular_proxima(self):
        """Calcula la próxima ejecución según la frecuencia (RF-48)."""
        base = self.ultima_ejecucion or timezone.now()
        delta = {"DIARIA": 1, "SEMANAL": 7, "MENSUAL": 30}[self.frecuencia]
        self.proxima_ejecucion = base + timezone.timedelta(days=delta)
        self.save(update_fields=["proxima_ejecucion"])
        return self.proxima_ejecucion

    def esta_vencida(self):
        return bool(self.activa and self.proxima_ejecucion
                    and self.proxima_ejecucion <= timezone.now())
