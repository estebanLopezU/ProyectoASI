from django.urls import path

from . import views

app_name = "mensajes"

urlpatterns = [
    path("", views.BandejaView.as_view(), name="bandeja"),
    path("nuevo/", views.nuevo_hilo, name="nuevo"),
    path("<int:pk>/", views.ver_hilo, name="hilo"),
    path("<int:pk>/intervenir/", views.intervenir_hilo, name="intervenir"),
]
