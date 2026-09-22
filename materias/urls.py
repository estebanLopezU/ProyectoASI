from django.urls import path

from . import views

app_name = "materias"

urlpatterns = [
    path("", views.CatalogoView.as_view(), name="catalogo"),
    path("proponer/", views.proponer_materia, name="proponer"),
    path("<int:pk>/editar/", views.editar_materia, name="editar"),
    path("panel/", views.PanelMateriasView.as_view(), name="panel"),
    path("solicitud/<int:pk>/<str:decision>/", views.revisar_solicitud, name="revisar"),
    # Maya curricular del estudiante (semáforo verde/amarillo/rojo)
    path("malla/<int:pk>/", views.malla_estudiante, name="malla"),
    path("malla/<int:pk>/editar/", views.editar_malla, name="malla_editar"),
]
