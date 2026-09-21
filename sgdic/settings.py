# =====================================================================
# SGDIC - Sistema de Gestión Departamental de Informática y Computación
# Proyecto Django (Django 4.2 LTS) - Configuración
# =====================================================================
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# Seguridad: en producción definir SECRET_KEY y DEBUG=0 en variables de entorno
# ---------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "SGDIC_SECRET_KEY",
    "django-insecure-sgdic-desarrollo-cambiar-en-produccion-1a2b3c4d5e",
)
DEBUG = os.environ.get("SGDIC_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]  # En producción restringir a los dominios reales

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps del SGDIC (arquitectura del documento técnico)
    "comun",
    "usuario",
    "cupos",
    "materias",
    "mensajes",
    "evaluaciones",
    "quejas",
    "reportes",
    "analitica",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "comun.middleware.ConfiguracionSGDIC",
]

ROOT_URLCONF = "sgdic.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "sgdic.wsgi.application"

# ---------------------------------------------------------------------
# Base de datos
# - En desarrollo: SQLite por defecto.
# - En producción (Render): DATABASE_URL inyectado automáticamente.
# - PostgreSQL manual: via variables SGDIC_DB_*.
# ---------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    # Producción (Render): usa DATABASE_URL directamente
    import dj_database_url
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)}
elif os.environ.get("SGDIC_DB_ENGINE") == "django.db.backends.postgresql":
    # PostgreSQL manual (arquitectura de producción via variables SGDIC_DB_*)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("SGDIC_DB_NAME", "sgdic"),
            "USER": os.environ.get("SGDIC_DB_USER", "sgdic"),
            "PASSWORD": os.environ.get("SGDIC_DB_PASSWORD", ""),
            "HOST": os.environ.get("SGDIC_DB_HOST", "localhost"),
            "PORT": os.environ.get("SGDIC_DB_PORT", "5432"),
        }
    }
else:
    # Desarrollo: SQLite sin dependencias externas
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "usuario.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 6}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "usuario:login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "usuario:login"

# Umbral de inasistencia (RN-08) y horas límite de respuesta (RN-19)
SGDIC_UMBRAL_INASISTENCIA = 20      # porcentaje
SGDIC_HORAS_RESPUESTA = 48          # horas
SGDIC_DIAS_ESCALAMIENTO = 3         # días (RN-10)
SGDIC_MIN_RESPUESTAS_ANONIMO = 5    # RN-05

# E-mail en consola para desarrollo (notificaciones)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
