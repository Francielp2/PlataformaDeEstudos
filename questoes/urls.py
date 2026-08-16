from django.urls import path

from . import views


app_name = "questoes"

urlpatterns = [
    path("", views.exercicios_lista, name="exercicios_lista"),
    path("iniciar/", views.iniciar_sequencia, name="iniciar_sequencia"),
    path("sequencia/", views.sequencia, name="sequencia"),
    path("sequencia/resumo/", views.sequencia_resumo, name="sequencia_resumo"),
    path("historico/", views.historico, name="historico"),
    path("respostas/<uuid:pk>/", views.resposta_detalhe, name="resposta_detalhe"),
    path("<uuid:pk>/", views.questao_detalhe, name="questao_detalhe"),
]
