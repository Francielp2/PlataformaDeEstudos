from django.urls import path

from . import views


app_name = "curriculo"

urlpatterns = [
    path("", views.materias_lista, name="materias_lista"),
    path("<slug:slug>/", views.materia_detalhe, name="materia_detalhe"),
]
