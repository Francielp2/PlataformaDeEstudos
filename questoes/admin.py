from django.contrib import admin

from .models import Alternativa, Questao, QuestaoConteudo, RespostaQuestao


class AlternativaInline(admin.TabularInline):
    model = Alternativa
    extra = 0


class QuestaoConteudoInline(admin.TabularInline):
    model = QuestaoConteudo
    extra = 0


@admin.register(Questao)
class QuestaoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "materia",
        "dificuldade",
        "status",
        "atualizado_em",
    )
    search_fields = ("codigo", "enunciado", "materia__nome")
    list_filter = ("materia", "dificuldade", "status", "tipo_fonte")
    ordering = ("codigo",)
    list_select_related = ("materia", "criado_por")
    inlines = (AlternativaInline, QuestaoConteudoInline)


@admin.register(Alternativa)
class AlternativaAdmin(admin.ModelAdmin):
    list_display = ("questao", "chave", "correta", "ordem")
    search_fields = ("questao__codigo", "texto")
    list_filter = ("correta",)
    ordering = ("questao__codigo", "ordem")
    list_select_related = ("questao",)


@admin.register(QuestaoConteudo)
class QuestaoConteudoAdmin(admin.ModelAdmin):
    list_display = ("questao", "conteudo", "principal")
    search_fields = ("questao__codigo", "conteudo__titulo")
    list_filter = ("principal", "conteudo__materia")
    list_select_related = ("questao", "conteudo", "conteudo__materia")


@admin.register(RespostaQuestao)
class RespostaQuestaoAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "questao",
        "alternativa_escolhida",
        "correta",
        "respondida_em",
    )
    search_fields = ("usuario__email", "questao__codigo", "questao__enunciado")
    list_filter = ("correta", "questao__materia")
    ordering = ("-respondida_em",)
    list_select_related = ("usuario", "questao", "alternativa_escolhida")
    readonly_fields = (
        "usuario",
        "questao",
        "alternativa_escolhida",
        "correta",
        "respondida_em",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
