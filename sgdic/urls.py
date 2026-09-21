# =====================================================================
# SGDIC - Enrutamiento raíz (RF-01 a RF-56)
# =====================================================================
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("notificaciones/", views.notificaciones, name="notificaciones"),
    path("notificaciones/<int:pk>/", views.notificacion_ir, name="notificacion_ir"),
    path("cuenta/", include("usuario.urls")),
    path("materias/", include("materias.urls")),
    path("cupos/", include("cupos.urls")),
    path("mensajes/", include("mensajes.urls")),
    path("evaluaciones/", include("evaluaciones.urls")),
    path("quejas/", include("quejas.urls")),
    path("reportes/", include("reportes.urls")),
    path("analitica/", include("analitica.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
