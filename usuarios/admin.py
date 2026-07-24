from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    ConsentimentoPrivacidade,
    PerfilEstudante,
    PreferenciaUsuario,
    Usuario,
)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "date_joined")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = ("id", "date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Informações pessoais",
            {"fields": ("first_name", "last_name", "anonimizado_em")},
        ),
        (
            "Permissões",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Datas importantes", {"fields": ("last_login", "date_joined")}),
        ("Identificação", {"fields": ("id",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(PerfilEstudante)
class PerfilEstudanteAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "apelido_ranking",
        "etapa_escolar",
        "fuso_horario",
        "criado_em",
        "atualizado_em",
    )
    list_filter = ("etapa_escolar", "fuso_horario", "criado_em")
    search_fields = ("usuario__email", "apelido_ranking")
    autocomplete_fields = ("usuario",)
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(PreferenciaUsuario)
class PreferenciaUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "exibir_ranking_publico",
        "permitir_percentil_privado",
        "notificacoes_email",
        "dificuldade_preferida",
        "atualizado_em",
    )
    list_filter = (
        "exibir_ranking_publico",
        "permitir_percentil_privado",
        "notificacoes_email",
        "dificuldade_preferida",
    )
    search_fields = ("usuario__email",)
    autocomplete_fields = ("usuario",)
    readonly_fields = ("atualizado_em",)


@admin.register(ConsentimentoPrivacidade)
class ConsentimentoPrivacidadeAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "tipo_documento",
        "versao_documento",
        "aceito",
        "registrado_em",
    )
    list_filter = ("tipo_documento", "versao_documento", "aceito")
    search_fields = ("usuario__email", "versao_documento", "ip_hash")
    autocomplete_fields = ("usuario",)
    readonly_fields = ("id", "registrado_em")
