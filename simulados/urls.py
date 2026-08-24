from django.urls import path

from . import views


app_name = "simulados"

urlpatterns = [
    path("", views.simulados_lista, name="simulados_lista"),
    path("meus/", views.meus_simulados, name="meus_simulados"),
    path("<slug:slug>/iniciar/", views.iniciar_simulado, name="iniciar_simulado"),
    path("tentativas/<uuid:pk>/questao/<int:ordem>/", views.tentativa_questao, name="tentativa_questao"),
    path("tentativas/<uuid:pk>/finalizar/", views.finalizar_tentativa, name="finalizar_tentativa"),
    path("tentativas/<uuid:pk>/resultado/", views.resultado_tentativa, name="resultado_tentativa"),
    path("tentativas/<uuid:pk>/revisao/", views.revisao_tentativa, name="revisao_tentativa"),
]
