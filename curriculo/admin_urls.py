from django.urls import path

from . import views


app_name = "curriculo_admin"

urlpatterns = [
    path("", views.admin_materias_lista, name="admin_materias_lista"),
    path("criar/", views.admin_materia_criar, name="admin_materia_criar"),
    path("<slug:slug>/", views.admin_materia_detalhe, name="admin_materia_detalhe"),
    path("<slug:slug>/editar/", views.admin_materia_editar, name="admin_materia_editar"),
    path(
        "<slug:slug>/alternar-status/",
        views.admin_materia_alternar_status,
        name="admin_materia_alternar_status",
    ),
]
