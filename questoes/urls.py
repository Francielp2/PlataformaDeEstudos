from django.urls import path

from . import views


app_name = "questoes"

urlpatterns = [
    path("", views.exercicios_lista, name="exercicios_lista"),
    path("iniciar/", views.iniciar_sequencia, name="iniciar_sequencia"),
    path("sequencia/", views.sequencia, name="sequencia"),
    path("sequencia/resultado/", views.sequencia_resultado, name="sequencia_resultado"),
    path("sequencia/resumo/", views.sequencia_resumo, name="sequencia_resumo"),
    path("desempenho/", views.desempenho, name="desempenho"),
    path("historico/", views.historico, name="historico"),
    path("respostas/<uuid:pk>/", views.resposta_detalhe, name="resposta_detalhe"),
    path("respostas/<uuid:pk>/resultado/", views.questao_resultado, name="questao_resultado"),
    path("<uuid:pk>/", views.questao_detalhe, name="questao_detalhe"),
]
