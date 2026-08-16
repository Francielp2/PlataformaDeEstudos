from django.contrib import admin

from .models import Conteudo, Materia


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


@admin.register(Conteudo)
class ConteudoAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "materia",
        "dificuldade",
        "status",
        "ordem_sugerida",
        "atualizado_em",
    )
    search_fields = ("titulo", "slug", "materia__nome")
    list_filter = ("materia", "dificuldade", "status")
    ordering = ("materia__ordem_exibicao", "ordem_sugerida", "titulo")
    list_select_related = ("materia", "pai", "criado_por")
