# =====================================================================
# App usuario: modelo Usuario con rol (RBAC) - RF-01, RF-02, RF-03
# =====================================================================
from django.contrib.auth.models import AbstractUser
from django.db import models

ROLES = [
    ("ESTUDIANTE", "Estudiante"),
    ("DOCENTE", "Docente"),
    ("SECRETARIA", "Secretaría"),
    ("DEPARTAMENTO", "Departamento"),
    ("ADMIN", "Administrador"),
]


class Usuario(AbstractUser):
    """Usuario institucional con rol para el control de acceso RBAC."""

    rol = models.CharField("rol", max_length=15, choices=ROLES, default="ESTUDIANTE")
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    codigo_institucional = models.CharField("código institucional", max_length=20, blank=True)
    semestre = models.PositiveSmallIntegerField("semestre", default=1)
    promedio = models.DecimalField("promedio acumulado", max_digits=3, decimal_places=2,
                                   default=0)
    area = models.CharField("área / especialidad", max_length=80, blank=True)
    notificar_correo = models.BooleanField("recibir notificaciones por correo", default=True)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        nombre = self.get_full_name() or self.username
        return f"{nombre} ({self.get_rol_display()})"

    # Atajos de rol -----------------------------------------------------
    @property
    def es_estudiante(self):
        return self.rol == "ESTUDIANTE"

    @property
    def es_docente(self):
        return self.rol == "DOCENTE"

    @property
    def es_secretaria(self):
        return self.rol == "SECRETARIA"

    @property
    def es_departamento(self):
        return self.rol == "DEPARTAMENTO"

    @property
    def es_staff_sgdic(self):
        return self.rol in ("SECRETARIA", "DEPARTAMENTO", "ADMIN")
