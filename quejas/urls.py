from django.urls import path

from . import views

app_name = "quejas"

urlpatterns = [
    path("", views.mis_quejas, name="mis_quejas"),
    path("nueva/", views.radicar, name="radicar"),
    path("gestion/", views.panel_gestion, name="panel"),
    path("escalamientos/", views.casos_vencidos, name="vencidos"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/gestionar/", views.gestionar, name="gestionar"),
    path("<int:pk>/confirmar/", views.confirmar, name="confirmar"),
    path("<int:pk>/reabrir/", views.reabrir, name="reabrir"),
]
