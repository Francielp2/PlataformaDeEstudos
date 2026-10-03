import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from curriculo.models import Conteudo


YOUTUBE_ID_REGEX = r"^[A-Za-z0-9_-]{11}$"

validar_youtube_id = RegexValidator(
    YOUTUBE_ID_REGEX,
    "Identificador do YouTube inválido.",
)


class VideoConteudo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conteudo = models.ForeignKey(
        Conteudo,
        on_delete=models.PROTECT,
        related_name="videos",
    )
    youtube_id = models.CharField(max_length=11, validators=[validar_youtube_id])
    titulo = models.CharField(max_length=255)
    canal_nome = models.CharField(max_length=255)
    canal_url = models.URLField(max_length=500)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    nota_curador = models.TextField(blank=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    metadados_atualizados_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="videos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem", "criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["conteudo", "youtube_id"],
                name="unique_video_por_conteudo",
            ),
        ]
        indexes = [
            models.Index(fields=["conteudo", "ativo", "ordem"]),
        ]
        verbose_name = "vídeo de conteúdo"
        verbose_name_plural = "vídeos de conteúdo"

    def __str__(self):
        return f"{self.titulo} ({self.canal_nome})"

    @property
    def url_youtube(self):
        return f"https://www.youtube.com/watch?v={self.youtube_id}"

    @property
    def url_embed(self):
        return f"https://www.youtube-nocookie.com/embed/{self.youtube_id}"


class ProgressoVideo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="progressos_video",
    )
    video = models.ForeignKey(
        VideoConteudo,
        on_delete=models.PROTECT,
        related_name="progressos",
    )
    ultima_posicao_segundos = models.PositiveIntegerField(default=0)
    segundos_assistidos_total = models.PositiveIntegerField(default=0)
    iniciado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "video"],
                name="unique_progresso_usuario_video",
            ),
        ]
        indexes = [
            models.Index(fields=["usuario", "-atualizado_em"]),
        ]
        verbose_name = "progresso em vídeo"
        verbose_name_plural = "progressos em vídeos"

    def __str__(self):
        return f"{self.usuario} - {self.video}"


class SessaoVideo(models.Model):
    # O id é gerado pelo navegador (crypto.randomUUID), um por carregamento de player.
    id = models.UUIDField(primary_key=True, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sessoes_video",
    )
    video = models.ForeignKey(
        VideoConteudo,
        on_delete=models.PROTECT,
        related_name="sessoes",
    )
    inicio_segundos = models.PositiveIntegerField()
    fim_segundos = models.PositiveIntegerField()
    segundos_assistidos = models.PositiveIntegerField()
    iniciado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-iniciado_em"]
        indexes = [
            models.Index(fields=["usuario", "-iniciado_em"]),
        ]
        verbose_name = "sessão de vídeo"
        verbose_name_plural = "sessões de vídeo"

    def __str__(self):
        return f"{self.usuario} - {self.video} em {self.iniciado_em:%d/%m/%Y %H:%M}"
