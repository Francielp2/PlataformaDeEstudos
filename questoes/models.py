import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from curriculo.models import Conteudo, Materia


class Questao(models.Model):
    class DificuldadeQuestao(models.TextChoices):
        FACIL = "easy", "Fácil"
        MEDIA = "medium", "Média"
        DIFICIL = "hard", "Difícil"

    class TipoFonte(models.TextChoices):
        ORIGINAL = "original", "Original"
        ENEM = "enem", "ENEM"
        VESTIBULAR = "vestibular", "Vestibular"
        ADAPTADA = "adapted", "Adaptada"
        OUTRA = "other", "Outra"

    class StatusQuestao(models.TextChoices):
        RASCUNHO = "draft", "Rascunho"
        PUBLICADA = "published", "Publicada"
        ARQUIVADA = "archived", "Arquivada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=40, unique=True)
    materia = models.ForeignKey(
        Materia,
        on_delete=models.PROTECT,
        related_name="questoes",
    )
    enunciado = models.TextField()
    explicacao = models.TextField(blank=True)
    dificuldade = models.CharField(
        max_length=16,
        choices=DificuldadeQuestao.choices,
        default=DificuldadeQuestao.MEDIA,
    )
    tipo_fonte = models.CharField(
        max_length=16,
        choices=TipoFonte.choices,
        default=TipoFonte.ORIGINAL,
    )
    fonte_nome = models.CharField(max_length=120, blank=True)
    fonte_ano = models.PositiveSmallIntegerField(null=True, blank=True)
    fonte_url = models.URLField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=StatusQuestao.choices,
        default=StatusQuestao.RASCUNHO,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="questoes_criadas",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]
        indexes = [
            models.Index(fields=["status", "dificuldade"]),
            models.Index(fields=["materia", "status"]),
        ]
        verbose_name = "questão"
        verbose_name_plural = "questões"

    def __str__(self):
        return self.codigo

    def clean(self):
        super().clean()
        self.codigo = " ".join((self.codigo or "").split()).upper()
        if not self.codigo:
            raise ValidationError({"codigo": "Informe o código da questão."})
        if not (self.enunciado or "").strip():
            raise ValidationError({"enunciado": "Informe o enunciado da questão."})

    def validar_publicacao(self):
        erros = {}
        if not self.materia_id:
            erros["materia"] = "Informe a matéria da questão."
        if not (self.enunciado or "").strip():
            erros["enunciado"] = "Informe o enunciado da questão."

        alternativas = list(self.alternativas.all())
        if len(alternativas) < 2:
            erros["alternativas"] = "A questão publicada deve ter pelo menos 2 alternativas."
        corretas = [alternativa for alternativa in alternativas if alternativa.correta]
        if len(corretas) != 1:
            erros["alternativas_corretas"] = (
                "A questão publicada deve ter exatamente 1 alternativa correta."
            )

        relacoes = list(self.questao_conteudos.select_related("conteudo").all())
        if not relacoes:
            erros["conteudos"] = "A questão publicada deve ter pelo menos 1 conteúdo."
        elif any(relacao.conteudo.materia_id != self.materia_id for relacao in relacoes):
            erros["conteudos"] = (
                "Todos os conteúdos relacionados devem pertencer à matéria da questão."
            )

        principais = [relacao for relacao in relacoes if relacao.principal]
        if len(principais) != 1:
            erros["conteudo_principal"] = (
                "A questão publicada deve ter exatamente 1 conteúdo principal."
            )

        if erros:
            raise ValidationError(erros)

    def publicar(self):
        self.validar_publicacao()
        self.status = self.StatusQuestao.PUBLICADA
        self.save(update_fields=["status", "atualizado_em"])

    def save(self, *args, **kwargs):
        self.codigo = " ".join((self.codigo or "").split()).upper()
        super().save(*args, **kwargs)


class Alternativa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    questao = models.ForeignKey(
        Questao,
        on_delete=models.CASCADE,
        related_name="alternativas",
    )
    chave = models.CharField(max_length=4)
    texto = models.TextField()
    correta = models.BooleanField(default=False)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["questao", "chave"],
                name="unique_alternativa_chave_por_questao",
            ),
            models.UniqueConstraint(
                fields=["questao", "ordem"],
                name="unique_alternativa_ordem_por_questao",
            ),
        ]
        verbose_name = "alternativa"
        verbose_name_plural = "alternativas"

    def __str__(self):
        return f"{self.questao.codigo} - {self.chave}"

    def clean(self):
        super().clean()
        self.chave = " ".join((self.chave or "").split()).upper()
        if not self.chave:
            raise ValidationError({"chave": "Informe a chave da alternativa."})
        if not (self.texto or "").strip():
            raise ValidationError({"texto": "Informe o texto da alternativa."})

    def save(self, *args, **kwargs):
        self.chave = " ".join((self.chave or "").split()).upper()
        super().save(*args, **kwargs)


class QuestaoConteudo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    questao = models.ForeignKey(
        Questao,
        on_delete=models.CASCADE,
        related_name="questao_conteudos",
    )
    conteudo = models.ForeignKey(
        Conteudo,
        on_delete=models.PROTECT,
        related_name="questao_conteudos",
    )
    principal = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["questao", "conteudo"],
                name="unique_conteudo_por_questao",
            ),
            models.UniqueConstraint(
                fields=["questao"],
                condition=Q(principal=True),
                name="unique_conteudo_principal_por_questao",
            ),
        ]
        verbose_name = "conteúdo da questão"
        verbose_name_plural = "conteúdos da questão"

    def __str__(self):
        return f"{self.questao.codigo} - {self.conteudo.titulo}"

    def clean(self):
        super().clean()
        if (
            self.questao_id
            and self.conteudo_id
            and self.questao.materia_id != self.conteudo.materia_id
        ):
            raise ValidationError(
                {"conteudo": "O conteúdo deve pertencer à matéria da questão."}
            )


class RespostaQuestao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="respostas_questoes",
    )
    questao = models.ForeignKey(
        Questao,
        on_delete=models.PROTECT,
        related_name="respostas",
    )
    alternativa_escolhida = models.ForeignKey(
        Alternativa,
        on_delete=models.PROTECT,
        related_name="respostas_recebidas",
    )
    correta = models.BooleanField()
    respondida_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-respondida_em"]
        indexes = [
            models.Index(fields=["usuario", "-respondida_em"]),
            models.Index(fields=["questao", "-respondida_em"]),
        ]
        verbose_name = "resposta de questão"
        verbose_name_plural = "respostas de questões"

    def __str__(self):
        return f"{self.usuario} - {self.questao.codigo}"

    def clean(self):
        super().clean()
        if (
            self.questao_id
            and self.alternativa_escolhida_id
            and self.alternativa_escolhida.questao_id != self.questao_id
        ):
            raise ValidationError(
                {
                    "alternativa_escolhida": (
                        "A alternativa escolhida não pertence à questão."
                    )
                }
            )

    def save(self, *args, **kwargs):
        if self.alternativa_escolhida_id:
            self.correta = self.alternativa_escolhida.correta
        super().save(*args, **kwargs)
