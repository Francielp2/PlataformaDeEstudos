from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("exercicios/", include("questoes.urls")),
    path("simulados/", include("simulados.urls")),
    path("estudos/", include("estudos.urls")),
    path("usuarios/administracao/questoes/", include("questoes.admin_urls")),
    path("usuarios/administracao/simulados/", include("simulados.admin_urls")),
    path("materias/", include("curriculo.urls")),
    path("usuarios/administracao/materias/", include("curriculo.admin_urls")),
    path("usuarios/", include("usuarios.urls")),
    path("", include("core.urls")),
]
