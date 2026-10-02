from django.urls import path

from . import views

app_name = "investigacion"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.crear, name="crear"),
    path("panel/", views.panel, name="panel"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/activar/", views.toggle_activo, name="toggle_activo"),
    path("<int:pk>/solicitar/", views.solicitar, name="solicitar"),
    path("inscripcion/<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("inscripcion/<int:pk>/responder/", views.responder, name="responder"),
]