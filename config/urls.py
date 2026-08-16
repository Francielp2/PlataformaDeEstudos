from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("materias/", include("curriculo.urls")),
    path("usuarios/administracao/materias/", include("curriculo.admin_urls")),
    path("usuarios/", include("usuarios.urls")),
    path("", include("core.urls")),
]
