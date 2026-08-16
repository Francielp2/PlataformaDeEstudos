from django.urls import path

from . import views


app_name = "estudos"

urlpatterns = [
    path("minha-lista/", views.minha_lista, name="minha_lista"),
    path("estudados/", views.conteudos_estudados, name="conteudos_estudados"),
    path(
        "minha-lista/item/<uuid:pk>/remover/",
        views.remover_item_minha_lista,
        name="remover_item_minha_lista",
    ),
    path(
        "minha-lista/materia/<uuid:pk>/alternar/",
        views.alternar_materia_minha_lista,
        name="alternar_materia_minha_lista",
    ),
    path(
        "minha-lista/conteudo/<uuid:pk>/alternar/",
        views.alternar_conteudo_minha_lista,
        name="alternar_conteudo_minha_lista",
    ),
    path(
        "minha-lista/questao/<uuid:pk>/alternar/",
        views.alternar_questao_minha_lista,
        name="alternar_questao_minha_lista",
    ),
    path(
        "estudados/conteudo/<uuid:pk>/alternar/",
        views.alternar_conteudo_estudado,
        name="alternar_conteudo_estudado",
    ),
]
