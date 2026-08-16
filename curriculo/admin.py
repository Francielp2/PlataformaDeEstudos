from django.contrib import admin

from .models import Materia


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "ativa",
        "ordem_exibicao",
        "criado_por",
        "criado_em",
    )
    search_fields = ("nome", "slug")
    list_filter = ("ativa",)
    ordering = ("ordem_exibicao", "nome")
