from django.contrib import admin

from .models import ConteudoEstudado, ItemMinhaLista


@admin.register(ItemMinhaLista)
class ItemMinhaListaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo_display", "rotulo", "adicionado_em")
    list_filter = ("adicionado_em",)
    search_fields = (
        "usuario__email",
        "materia__nome",
        "conteudo__titulo",
        "questao__codigo",
    )
    readonly_fields = ("adicionado_em",)


@admin.register(ConteudoEstudado)
class ConteudoEstudadoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "conteudo", "marcado_em")
    list_filter = ("marcado_em", "conteudo__materia", "conteudo__dificuldade")
    search_fields = ("usuario__email", "conteudo__titulo", "conteudo__materia__nome")
    readonly_fields = ("marcado_em",)
