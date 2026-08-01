from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    PerfilEstudante,
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
            {"fields": ("first_name", "last_name")},
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
        "etapa_escolar",
        "criado_em",
        "atualizado_em",
    )
    list_filter = ("etapa_escolar", "criado_em")
    search_fields = ("usuario__email", "usuario__first_name", "usuario__last_name")
    autocomplete_fields = ("usuario",)
    readonly_fields = ("criado_em", "atualizado_em")
