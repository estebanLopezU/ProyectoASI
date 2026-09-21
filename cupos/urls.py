from django.urls import path

from . import views

app_name = "cupos"

urlpatterns = [
    path("", views.OfertasView.as_view(), name="ofertas"),
    path("mis-solicitudes/", views.MisSolicitudesView.as_view(), name="mis_solicitudes"),
    path("inscripciones/", views.MisInscripcionesView.as_view(), name="inscripciones"),
    path("lista-espera/", views.ListaEsperaView.as_view(), name="lista_espera"),
    path("procesar-pendientes/", views.procesar_pendientes, name="procesar_pendientes"),
    path("oferta/<int:oferta_id>/solicitar/", views.solicitar_cupo, name="solicitar"),
    path("inscripcion/<int:inscripcion_id>/confirmar/", views.confirmar_cupo, name="confirmar"),
]
