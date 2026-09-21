from django.urls import path

from . import views

app_name = "evaluaciones"

urlpatterns = [
    path("faltas/", views.mis_faltas, name="mis_faltas"),
    path("faltas/<int:pk>/justificar/", views.justificar_falta, name="justificar"),
    path("faltas/revisar/", views.revisar_justificaciones, name="revisar_lista"),
    path("faltas/<int:pk>/revisar/", views.revisar_falta, name="revisar"),
    path("inasistencia/", views.panel_inasistencia, name="panel_inasistencia"),
    path("sesiones/", views.registrar_asistencia, name="registrar_asistencia"),
    path("sesiones/<int:pk>/", views.registrar_asistencia, name="asistencia_sesion"),
    path("evaluacion/", views.mis_invitaciones, name="mis_invitaciones"),
    path("evaluacion/<int:pk>/responder/", views.responder_evaluacion, name="responder"),
    path("evaluacion/resultados/", views.resultados_docente, name="resultados"),
    path("evaluacion/periodos/", views.gestionar_periodos, name="periodos"),
    path("evaluacion/periodos/<int:pk>/notificar/", views.enviar_recordatorios, name="recordatorios"),
]
