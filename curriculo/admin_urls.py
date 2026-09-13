from django.urls import path

from . import views


app_name = "curriculo_admin"

urlpatterns = [
    path("", views.admin_materias_lista, name="admin_materias_lista"),
    path("conteudos/", views.admin_conteudos_lista, name="admin_conteudos_lista"),
    path(
        "conteudos/importar-json/",
        views.admin_conteudos_importar_json,
        name="admin_conteudos_importar_json",
    ),
    path(
        "conteudos/publicar-rascunhos/",
        views.admin_conteudos_publicar_rascunhos,
        name="admin_conteudos_publicar_rascunhos",
    ),
    path("conteudos/criar/", views.admin_conteudo_criar, name="admin_conteudo_criar"),
    path("conteudos/<uuid:pk>/", views.admin_conteudo_detalhe, name="admin_conteudo_detalhe"),
    path("conteudos/<uuid:pk>/editar/", views.admin_conteudo_editar, name="admin_conteudo_editar"),
    path(
        "conteudos/<uuid:pk>/status/<slug:status>/",
        views.admin_conteudo_alterar_status,
        name="admin_conteudo_alterar_status",
    ),
    path(
        "importar-json/",
        views.admin_materias_importar_json,
        name="admin_materias_importar_json",
    ),
    path(
        "padroes-json/",
        views.admin_padroes_importacao_json,
        name="admin_padroes_importacao_json",
    ),
    path("criar/", views.admin_materia_criar, name="admin_materia_criar"),
    path("<slug:slug>/", views.admin_materia_detalhe, name="admin_materia_detalhe"),
    path("<slug:slug>/editar/", views.admin_materia_editar, name="admin_materia_editar"),
    path(
        "<slug:slug>/alternar-status/",
        views.admin_materia_alternar_status,
        name="admin_materia_alternar_status",
    ),
]
