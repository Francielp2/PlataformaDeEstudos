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
