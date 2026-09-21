from django.urls import path

from . import views

app_name = "usuario"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("perfil/", views.perfil, name="perfil"),
    # Recuperación de contraseña (RF-03)
    path("password/", views.PasswordResetView.as_view(), name="password_reset"),
    path("password/hecho/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/cambiar/", views.PasswordChangeView.as_view(), name="password_change"),
    path("password/cambiar/hecho/", views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path(
        "password/confirmar/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/confirmar/hecho/",
        views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
