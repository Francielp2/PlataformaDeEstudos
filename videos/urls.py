from django.urls import path

from . import views


app_name = "videos"

urlpatterns = [
    path("historico/", views.historico, name="historico"),
    path("<uuid:pk>/progresso/", views.registrar_progresso_video, name="registrar_progresso"),
]
