from django.contrib import admin

from .models import (
    AlternativaSimulado,
    QuestaoSimulado,
    QuestaoSimuladoConteudo,
    RespostaSimulado,
    Simulado,
    TentativaSimulado,
)


class AlternativaSimuladoInline(admin.TabularInline):
    model = AlternativaSimulado
    extra = 0


class QuestaoSimuladoConteudoInline(admin.TabularInline):
    model = QuestaoSimuladoConteudo
    extra = 0


@admin.register(Simulado)
class SimuladoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tipo", "materia", "status", "tempo_limite", "atualizado_em")
    search_fields = ("titulo", "descricao", "materia__nome")
    list_filter = ("tipo", "status", "materia")
    prepopulated_fields = {"slug": ("titulo",)}
    list_select_related = ("materia", "criado_por")


@admin.register(QuestaoSimulado)
class QuestaoSimuladoAdmin(admin.ModelAdmin):
    list_display = ("simulado", "ordem", "codigo_origem", "origem", "dificuldade")
    search_fields = ("simulado__titulo", "codigo_origem", "enunciado")
    list_filter = ("origem", "dificuldade", "tipo_fonte")
    list_select_related = ("simulado", "questao_origem")
    inlines = (AlternativaSimuladoInline, QuestaoSimuladoConteudoInline)


@admin.register(AlternativaSimulado)
class AlternativaSimuladoAdmin(admin.ModelAdmin):
    list_display = ("questao_simulado", "chave", "correta", "ordem")
    search_fields = ("questao_simulado__enunciado", "texto")
    list_filter = ("correta",)
    list_select_related = ("questao_simulado",)


@admin.register(QuestaoSimuladoConteudo)
class QuestaoSimuladoConteudoAdmin(admin.ModelAdmin):
    list_display = ("questao_simulado", "conteudo_titulo", "materia_nome", "principal")
    search_fields = ("questao_simulado__enunciado", "conteudo_titulo", "materia_nome")
    list_filter = ("principal", "materia_nome")
    list_select_related = ("questao_simulado", "conteudo")


@admin.register(TentativaSimulado)
class TentativaSimuladoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "simulado", "status", "total_acertos", "total_questoes", "percentual", "iniciada_em")
    search_fields = ("usuario__email", "simulado__titulo")
    list_filter = ("status", "simulado")
    list_select_related = ("usuario", "simulado")
    readonly_fields = ("iniciada_em", "finalizada_em", "total_questoes", "total_acertos", "percentual", "tempo_gasto")


@admin.register(RespostaSimulado)
class RespostaSimuladoAdmin(admin.ModelAdmin):
    list_display = ("tentativa", "questao_simulado", "alternativa_chave", "correta", "respondida_em")
    search_fields = ("tentativa__usuario__email", "questao_simulado__enunciado", "alternativa_texto")
    list_filter = ("correta",)
    list_select_related = ("tentativa", "questao_simulado", "alternativa_escolhida")
    readonly_fields = ("alternativa_chave", "alternativa_texto", "correta", "respondida_em")
