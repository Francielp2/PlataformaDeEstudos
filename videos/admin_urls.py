from django.urls import path

from . import views


app_name = "videos_admin"

urlpatterns = [
    path("", views.admin_videos_lista, name="lista"),
    path("criar/", views.admin_video_criar, name="criar"),
    path("preview/", views.admin_video_preview, name="preview"),
    path("importar-json/", views.admin_importar_json, name="importar_json"),
    path("<uuid:pk>/", views.admin_video_detalhe, name="detalhe"),
    path("<uuid:pk>/editar/", views.admin_video_editar, name="editar"),
    path("<uuid:pk>/alternar-status/", views.admin_video_alternar_status, name="alternar_status"),
    path("<uuid:pk>/atualizar-dados/", views.admin_video_atualizar_dados, name="atualizar_dados"),
]
