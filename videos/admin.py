from django.contrib import admin

from .models import ProgressoVideo, SessaoVideo, VideoConteudo


@admin.register(VideoConteudo)
class VideoConteudoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "canal_nome", "conteudo", "ordem", "ativo", "criado_em")
    list_filter = ("ativo", "conteudo__materia")
    search_fields = ("titulo", "canal_nome", "youtube_id", "conteudo__titulo")
    readonly_fields = ("criado_em", "atualizado_em", "metadados_atualizados_em")


@admin.register(ProgressoVideo)
class ProgressoVideoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "video", "percentual", "concluido", "atualizado_em")
    list_filter = ("concluido", "video__conteudo__materia")
    search_fields = ("usuario__email", "video__titulo")
    readonly_fields = ("iniciado_em", "atualizado_em")


@admin.register(SessaoVideo)
class SessaoVideoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "video", "inicio_segundos", "fim_segundos", "segundos_assistidos", "iniciado_em")
    list_filter = ("iniciado_em",)
    search_fields = ("usuario__email", "video__titulo")
    readonly_fields = ("iniciado_em", "atualizado_em")
