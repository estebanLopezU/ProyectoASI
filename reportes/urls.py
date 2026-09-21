from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("<int:pk>/generar/", views.generar, name="generar"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/descargar/", views.descargar, name="descargar"),
    path("programaciones/", views.programaciones, name="programaciones"),
    path("programaciones/ejecutar/", views.ejecutar_programaciones, name="ejecutar"),
]
