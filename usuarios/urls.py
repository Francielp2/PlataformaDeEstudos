from django.urls import path

from . import views


app_name = "usuarios"

urlpatterns = [
    path("cadastro/", views.cadastro, name="cadastro"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("painel/", views.painel, name="painel"),
    path("estudante/", views.painel_estudante, name="painel_estudante"),
    path("perfil/", views.perfil, name="perfil"),
    path(
        "funcionalidades/<slug:slug>/",
        views.funcionalidade_futura,
        name="funcionalidade_futura",
    ),
    path("administracao/", views.admin_painel, name="admin_painel"),
    path(
        "administracao/usuarios/",
        views.admin_usuarios_lista,
        name="admin_usuarios_lista",
    ),
    path(
        "administracao/usuarios/criar/",
        views.admin_usuario_criar,
        name="admin_usuario_criar",
    ),
    path(
        "administracao/usuarios/<uuid:pk>/",
        views.admin_usuario_detalhe,
        name="admin_usuario_detalhe",
    ),
    path(
        "administracao/usuarios/<uuid:pk>/editar/",
        views.admin_usuario_editar,
        name="admin_usuario_editar",
    ),
    path(
        "administracao/usuarios/<uuid:pk>/ativar/",
        views.admin_usuario_ativar,
        name="admin_usuario_ativar",
    ),
    path(
        "administracao/usuarios/<uuid:pk>/excluir/",
        views.admin_usuario_excluir,
        name="admin_usuario_excluir",
    ),
    path(
        "administracao/funcionalidades/<slug:slug>/",
        views.admin_funcionalidade_futura,
        name="admin_funcionalidade_futura",
    ),
]
