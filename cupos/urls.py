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
    # Preinscripción de asignaturas (RN-13, RN-14)
    path("preinscripcion/", views.PreinscripcionView.as_view(), name="preinscripcion"),
    path("preinscripcion/materia/<int:materia_id>/agregar/",
         views.preinscribir_materia, name="preinscribir"),
    path("preinscripcion/<int:preinscripcion_id>/quitar/",
         views.quitar_preinscripcion, name="quitar_preinscripcion"),
    path("preinscripcion/<int:preinscripcion_id>/<str:direccion>/",
         views.mover_prioridad, name="mover_prioridad"),
    path("preinscripcion/preferencias/", views.guardar_preferencias, name="preferencias"),
    path("preinscripcion/enviar/", views.enviar_preinscripcion, name="enviar_preinscripcion"),
    # Franja horaria semanal (calendario de clases)
    path("horario/", views.mi_horario, name="mi_horario"),
]
