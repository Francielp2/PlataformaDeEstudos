from django.urls import path

from . import views


app_name = "simulados_admin"

urlpatterns = [
    path("", views.admin_simulados_lista, name="admin_simulados_lista"),
    path(
        "publicar-rascunhos/",
        views.admin_simulados_publicar_rascunhos,
        name="admin_simulados_publicar_rascunhos",
    ),
    path("criar/", views.admin_simulado_criar, name="admin_simulado_criar"),
    path("<uuid:pk>/", views.admin_simulado_detalhe, name="admin_simulado_detalhe"),
    path("<uuid:pk>/editar/", views.admin_simulado_editar, name="admin_simulado_editar"),
    path("<uuid:pk>/publicar/", views.admin_simulado_publicar, name="admin_simulado_publicar"),
    path("<uuid:pk>/arquivar/", views.admin_simulado_arquivar, name="admin_simulado_arquivar"),
    path("<uuid:pk>/duplicar/", views.admin_simulado_duplicar, name="admin_simulado_duplicar"),
    path("<uuid:pk>/questoes/", views.admin_simulado_questoes, name="admin_simulado_questoes"),
    path("<uuid:pk>/questoes/banco/", views.admin_adicionar_questoes_banco, name="admin_adicionar_questoes_banco"),
    path("<uuid:pk>/questoes/nova/", views.admin_nova_questao_simulado, name="admin_nova_questao_simulado"),
    path("<uuid:pk>/questoes/importar-json/", views.admin_importar_json, name="admin_importar_json"),
    path("<uuid:pk>/questoes/<uuid:questao_pk>/remover/", views.admin_remover_questao_simulado, name="admin_remover_questao_simulado"),
    path("<uuid:pk>/questoes/<uuid:questao_pk>/mover/<str:direcao>/", views.admin_mover_questao_simulado, name="admin_mover_questao_simulado"),
    path("<uuid:pk>/resultados/", views.admin_resultados_simulado, name="admin_resultados_simulado"),
    path("resultados/<uuid:tentativa_pk>/", views.admin_resultado_detalhe, name="admin_resultado_detalhe"),
]
