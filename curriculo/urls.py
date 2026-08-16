from django.urls import path

from . import views


app_name = "curriculo"

urlpatterns = [
    path("", views.materias_lista, name="materias_lista"),
    path("conteudos/", views.conteudos_lista, name="conteudos_lista"),
    path(
        "<slug:materia_slug>/conteudos/<slug:conteudo_slug>/",
        views.conteudo_detalhe,
        name="conteudo_detalhe",
    ),
    path("<slug:slug>/", views.materia_detalhe, name="materia_detalhe"),
]
