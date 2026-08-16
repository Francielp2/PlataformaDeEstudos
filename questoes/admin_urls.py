from django.urls import path

from . import views


app_name = "questoes_admin"

urlpatterns = [
    path("", views.admin_questoes_lista, name="admin_questoes_lista"),
    path(
        "publicar-rascunhos/",
        views.admin_questoes_publicar_rascunhos,
        name="admin_questoes_publicar_rascunhos",
    ),
    path("criar/", views.admin_questao_criar, name="admin_questao_criar"),
    path("<uuid:pk>/", views.admin_questao_detalhe, name="admin_questao_detalhe"),
    path("<uuid:pk>/editar/", views.admin_questao_editar, name="admin_questao_editar"),
    path(
        "<uuid:pk>/status/<slug:status>/",
        views.admin_questao_alterar_status,
        name="admin_questao_alterar_status",
    ),
    path("respostas/", views.admin_respostas_lista, name="admin_respostas_lista"),
    path(
        "respostas/<uuid:pk>/",
        views.admin_resposta_detalhe,
        name="admin_resposta_detalhe",
    ),
]
