import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Materia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    descricao = models.TextField(blank=True)
    ordem_exibicao = models.PositiveSmallIntegerField(default=0)
    ativa = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="materias_criadas",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem_exibicao", "nome"]
        indexes = [
            models.Index(fields=["ativa", "ordem_exibicao"]),
        ]
        verbose_name = "matéria"
        verbose_name_plural = "matérias"

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        self.nome = " ".join((self.nome or "").split())
        if not self.nome:
            raise ValidationError({"nome": "Informe o nome da matéria."})

        duplicada = Materia.objects.filter(nome__iexact=self.nome)
        if self.pk:
            duplicada = duplicada.exclude(pk=self.pk)
        if duplicada.exists():
            raise ValidationError({"nome": "Já existe uma matéria com este nome."})

    def _gerar_slug_unico(self):
        base = slugify(self.nome)[:80] or "materia"
        slug = base
        contador = 2
        while Materia.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            sufixo = f"-{contador}"
            slug = f"{base[:80 - len(sufixo)]}{sufixo}"
            contador += 1
        return slug

    def save(self, *args, **kwargs):
        self.nome = " ".join((self.nome or "").split())
        if not self.slug:
            self.slug = self._gerar_slug_unico()
        super().save(*args, **kwargs)


class Conteudo(models.Model):
    class DificuldadeConteudo(models.TextChoices):
        BASICO = "basic", "Básico"
        INTERMEDIARIO = "intermediate", "Intermediário"
        AVANCADO = "advanced", "Avançado"

    class StatusConteudo(models.TextChoices):
        RASCUNHO = "draft", "Rascunho"
        PUBLICADO = "published", "Publicado"
        ARQUIVADO = "archived", "Arquivado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    materia = models.ForeignKey(
        Materia,
        on_delete=models.PROTECT,
        related_name="conteudos",
    )
    pai = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subconteudos",
    )
    slug = models.SlugField(max_length=100, blank=True)
    titulo = models.CharField(max_length=160)
    resumo = models.TextField()
    texto_estudo = models.TextField(blank=True)
    dificuldade = models.CharField(
        max_length=16,
        choices=DificuldadeConteudo.choices,
        default=DificuldadeConteudo.BASICO,
    )
    ordem_sugerida = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=StatusConteudo.choices,
        default=StatusConteudo.RASCUNHO,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="conteudos_criados",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem_sugerida", "titulo"]
        constraints = [
            models.UniqueConstraint(
                fields=["materia", "slug"],
                name="unique_conteudo_slug_por_materia",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "ordem_sugerida"]),
            models.Index(fields=["materia", "status", "ordem_sugerida"]),
        ]
        verbose_name = "conteúdo"
        verbose_name_plural = "conteúdos"

    def __str__(self):
        if self.materia_id:
            return f"{self.materia.nome} - {self.titulo}"
        return self.titulo

    def clean(self):
        super().clean()
        self.titulo = " ".join((self.titulo or "").split())
        if not self.titulo:
            raise ValidationError({"titulo": "Informe o título do conteúdo."})
        if not (self.resumo or "").strip():
            raise ValidationError({"resumo": "Informe o resumo do conteúdo."})

        if self.pai_id:
            if self.pk and self.pai_id == self.pk:
                raise ValidationError({"pai": "Um conteúdo não pode ser pai de si mesmo."})
            if self.materia_id and self.pai.materia_id != self.materia_id:
                raise ValidationError(
                    {"pai": "O conteúdo pai deve pertencer à mesma matéria."}
                )

        if self.pk and self.materia_id:
            filhos_inconsistentes = self.subconteudos.exclude(
                materia_id=self.materia_id
            ).exists()
            if filhos_inconsistentes:
                raise ValidationError(
                    {
                        "materia": (
                            "Não é possível alterar a matéria enquanto houver "
                            "subconteúdos em outra matéria."
                        )
                    }
                )

        self._validar_ciclo_hierarquia()

    def _validar_ciclo_hierarquia(self):
        if not self.pk or not self.pai_id:
            return

        ancestral = self.pai
        visitados = set()
        while ancestral:
            if ancestral.pk == self.pk:
                raise ValidationError(
                    {"pai": "A hierarquia de conteúdos não pode formar ciclos."}
                )
            if ancestral.pk in visitados:
                raise ValidationError(
                    {"pai": "A hierarquia de conteúdos não pode formar ciclos."}
                )
            visitados.add(ancestral.pk)
            ancestral = ancestral.pai

    def _gerar_slug_unico(self):
        base = slugify(self.titulo)[:100] or "conteudo"
        slug = base
        contador = 2
        while Conteudo.objects.filter(
            materia_id=self.materia_id,
            slug=slug,
        ).exclude(pk=self.pk).exists():
            sufixo = f"-{contador}"
            slug = f"{base[:100 - len(sufixo)]}{sufixo}"
            contador += 1
        return slug

    def save(self, *args, **kwargs):
        self.titulo = " ".join((self.titulo or "").split())
        if not self.slug:
            self.slug = self._gerar_slug_unico()
        super().save(*args, **kwargs)
