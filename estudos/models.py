import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from curriculo.models import Conteudo, Materia
from questoes.models import Questao


class ItemMinhaLista(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="itens_minha_lista",
    )
    materia = models.ForeignKey(
        Materia,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="itens_minha_lista",
    )
    conteudo = models.ForeignKey(
        Conteudo,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="itens_minha_lista",
    )
    questao = models.ForeignKey(
        Questao,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="itens_minha_lista",
    )
    adicionado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-adicionado_em"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        Q(materia__isnull=False)
                        & Q(conteudo__isnull=True)
                        & Q(questao__isnull=True)
                    )
                    | (
                        Q(materia__isnull=True)
                        & Q(conteudo__isnull=False)
                        & Q(questao__isnull=True)
                    )
                    | (
                        Q(materia__isnull=True)
                        & Q(conteudo__isnull=True)
                        & Q(questao__isnull=False)
                    )
                ),
                name="item_minha_lista_exatamente_um_alvo",
            ),
            models.UniqueConstraint(
                fields=["usuario", "materia"],
                condition=Q(materia__isnull=False),
                name="unique_minha_lista_usuario_materia",
            ),
            models.UniqueConstraint(
                fields=["usuario", "conteudo"],
                condition=Q(conteudo__isnull=False),
                name="unique_minha_lista_usuario_conteudo",
            ),
            models.UniqueConstraint(
                fields=["usuario", "questao"],
                condition=Q(questao__isnull=False),
                name="unique_minha_lista_usuario_questao",
            ),
        ]
        indexes = [
            models.Index(fields=["usuario", "-adicionado_em"]),
        ]
        verbose_name = "item da Minha Lista"
        verbose_name_plural = "itens da Minha Lista"

    def __str__(self):
        return f"{self.usuario} - {self.rotulo}"

    @property
    def tipo(self):
        if self.materia_id:
            return "materia"
        if self.conteudo_id:
            return "conteudo"
        if self.questao_id:
            return "questao"
        return ""

    @property
    def tipo_display(self):
        return {
            "materia": "Matéria",
            "conteudo": "Conteúdo",
            "questao": "Questão",
        }.get(self.tipo, "")

    @property
    def rotulo(self):
        if self.materia_id:
            return self.materia.nome
        if self.conteudo_id:
            return self.conteudo.titulo
        if self.questao_id:
            return self.questao.codigo
        return ""

    def clean(self):
        super().clean()
        alvos = [self.materia_id, self.conteudo_id, self.questao_id]
        if sum(1 for alvo in alvos if alvo) != 1:
            raise ValidationError(
                "Um item da Minha Lista deve ter exatamente um alvo."
            )


class ConteudoEstudado(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conteudos_estudados",
    )
    conteudo = models.ForeignKey(
        Conteudo,
        on_delete=models.PROTECT,
        related_name="marcacoes_estudado",
    )
    marcado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-marcado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "conteudo"],
                name="unique_conteudo_estudado_usuario_conteudo",
            ),
        ]
        indexes = [
            models.Index(fields=["usuario", "-marcado_em"]),
        ]
        verbose_name = "conteúdo estudado"
        verbose_name_plural = "conteúdos estudados"

    def __str__(self):
        return f"{self.usuario} - {self.conteudo}"
