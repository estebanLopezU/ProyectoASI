from django.urls import path

from . import views

app_name = "analitica"

urlpatterns = [
    path("", views.tablero, name="tablero"),
    path("detectar/", views.detectar, name="detectar"),
    path("simulador/", views.simulador, name="simulador"),
    path("predicciones/", views.predicciones, name="predicciones"),
]
