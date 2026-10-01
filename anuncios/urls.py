from django.urls import path

from . import views

app_name = "anuncios"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.crear, name="crear"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/retirar/", views.desactivar, name="desactivar"),
]
