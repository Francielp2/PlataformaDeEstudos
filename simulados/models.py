import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from curriculo.models import Conteudo, Materia
from questoes.models import Questao


class Simulado(models.Model):
    class TipoSimulado(models.TextChoices):
        GERAL = "GERAL", "Geral"
        POR_MATERIA = "POR_MATERIA", "Por matéria"

    class StatusSimulado(models.TextChoices):
        RASCUNHO = "draft", "Rascunho"
        PUBLICADO = "published", "Publicado"
        ARQUIVADO = "archived", "Arquivado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(
        max_length=16,
        choices=TipoSimulado.choices,
        default=TipoSimulado.GERAL,
    )
    materia = models.ForeignKey(
        Materia,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="simulados",
    )
    status = models.CharField(
        max_length=16,
        choices=StatusSimulado.choices,
        default=StatusSimulado.RASCUNHO,
    )
    tempo_limite = models.PositiveSmallIntegerField(null=True, blank=True)
    ordem_exibicao = models.PositiveSmallIntegerField(default=0)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="simulados_criados",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    publicado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["ordem_exibicao", "titulo"]
        indexes = [
            models.Index(fields=["status", "tipo", "ordem_exibicao"]),
            models.Index(fields=["materia", "status"]),
        ]
        verbose_name = "simulado"
        verbose_name_plural = "simulados"

    def __str__(self):
        return self.titulo

    def clean(self):
        super().clean()
        self.titulo = " ".join((self.titulo or "").split())
        if not self.titulo:
            raise ValidationError({"titulo": "Informe o título do simulado."})
        if self.tipo == self.TipoSimulado.POR_MATERIA and not self.materia_id:
            raise ValidationError({"materia": "Informe a matéria do simulado."})
        if self.tipo == self.TipoSimulado.GERAL and self.materia_id:
            raise ValidationError({"materia": "Simulados gerais não devem ter matéria."})

    def _gerar_slug_unico(self):
        base = slugify(self.titulo)[:180] or "simulado"
        slug = base
        contador = 2
        while Simulado.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            sufixo = f"-{contador}"
            slug = f"{base[:180 - len(sufixo)]}{sufixo}"
            contador += 1
        return slug

    def save(self, *args, **kwargs):
        self.titulo = " ".join((self.titulo or "").split())
        if not self.slug:
            self.slug = self._gerar_slug_unico()
        super().save(*args, **kwargs)

    @property
    def possui_tentativas(self):
        return self.tentativas.exists()

    def validar_publicacao(self):
        erros = {}
        questoes = list(
            self.questoes.prefetch_related("alternativas", "conteudos__conteudo").all()
        )
        if not questoes:
            erros["questoes"] = "O simulado precisa possuir pelo menos 1 questão."

        for questao in questoes:
            alternativas = list(questao.alternativas.all())
            if len(alternativas) < 2:
                erros[f"questao_{questao.ordem}_alternativas"] = (
                    f"Questão {questao.ordem}: informe pelo menos 2 alternativas."
                )
            if sum(1 for alternativa in alternativas if alternativa.correta) != 1:
                erros[f"questao_{questao.ordem}_correta"] = (
                    f"Questão {questao.ordem}: marque exatamente 1 alternativa correta."
                )
            relacoes = list(questao.conteudos.all())
            if not relacoes:
                erros[f"questao_{questao.ordem}_conteudos"] = (
                    f"Questão {questao.ordem}: informe pelo menos 1 conteúdo."
                )
            if sum(1 for relacao in relacoes if relacao.principal) != 1:
                erros[f"questao_{questao.ordem}_principal"] = (
                    f"Questão {questao.ordem}: informe exatamente 1 conteúdo principal."
                )
            if self.tipo == self.TipoSimulado.POR_MATERIA and self.materia_id:
                if any(relacao.conteudo.materia_id != self.materia_id for relacao in relacoes):
                    erros[f"questao_{questao.ordem}_materia"] = (
                        f"Questão {questao.ordem}: conteúdo fora da matéria do simulado."
                    )

        if erros:
            raise ValidationError(erros)

    def publicar(self):
        self.full_clean()
        self.validar_publicacao()
        self.status = self.StatusSimulado.PUBLICADO
        if not self.publicado_em:
            self.publicado_em = timezone.now()
        self.save(update_fields=["status", "publicado_em", "atualizado_em"])


class QuestaoSimulado(models.Model):
    class OrigemQuestao(models.TextChoices):
        BANCO = "BANCO", "Banco de questões"
        MANUAL = "MANUAL", "Criada no simulado"
        JSON = "JSON", "Importada por JSON"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    simulado = models.ForeignKey(
        Simulado,
        on_delete=models.CASCADE,
        related_name="questoes",
    )
    questao_origem = models.ForeignKey(
        Questao,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="snapshots_simulados",
    )
    origem = models.CharField(
        max_length=12,
        choices=OrigemQuestao.choices,
        default=OrigemQuestao.MANUAL,
    )
    codigo_origem = models.CharField(max_length=40, blank=True)
    enunciado = models.TextField()
    explicacao = models.TextField(blank=True)
    dificuldade = models.CharField(
        max_length=16,
        choices=Questao.DificuldadeQuestao.choices,
        default=Questao.DificuldadeQuestao.MEDIA,
    )
    tipo_fonte = models.CharField(
        max_length=16,
        choices=Questao.TipoFonte.choices,
        default=Questao.TipoFonte.ORIGINAL,
    )
    fonte_nome = models.CharField(max_length=120, blank=True)
    fonte_ano = models.PositiveSmallIntegerField(null=True, blank=True)
    fonte_url = models.URLField(blank=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordem", "criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["simulado", "ordem"],
                name="unique_questao_simulado_ordem",
            ),
        ]
        verbose_name = "questão do simulado"
        verbose_name_plural = "questões do simulado"

    def __str__(self):
        return f"{self.simulado} - Questão {self.ordem}"

    def clean(self):
        super().clean()
        if not (self.enunciado or "").strip():
            raise ValidationError({"enunciado": "Informe o enunciado da questão."})


class AlternativaSimulado(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    questao_simulado = models.ForeignKey(
        QuestaoSimulado,
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
                fields=["questao_simulado", "chave"],
                name="unique_alternativa_simulado_chave",
            ),
            models.UniqueConstraint(
                fields=["questao_simulado", "ordem"],
                name="unique_alternativa_simulado_ordem",
            ),
            models.UniqueConstraint(
                fields=["questao_simulado"],
                condition=Q(correta=True),
                name="unique_alternativa_correta_simulado",
            ),
        ]
        verbose_name = "alternativa do simulado"
        verbose_name_plural = "alternativas do simulado"

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


class QuestaoSimuladoConteudo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    questao_simulado = models.ForeignKey(
        QuestaoSimulado,
        on_delete=models.CASCADE,
        related_name="conteudos",
    )
    conteudo = models.ForeignKey(
        Conteudo,
        on_delete=models.PROTECT,
        related_name="questoes_simulado",
    )
    principal = models.BooleanField(default=False)
    conteudo_titulo = models.CharField(max_length=160)
    conteudo_slug = models.SlugField(max_length=100)
    materia_nome = models.CharField(max_length=80)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["questao_simulado", "conteudo"],
                name="unique_conteudo_questao_simulado",
            ),
            models.UniqueConstraint(
                fields=["questao_simulado"],
                condition=Q(principal=True),
                name="unique_conteudo_principal_questao_simulado",
            ),
        ]
        verbose_name = "conteúdo da questão do simulado"
        verbose_name_plural = "conteúdos da questão do simulado"

    def save(self, *args, **kwargs):
        if self.conteudo_id:
            if not self.conteudo_titulo:
                self.conteudo_titulo = self.conteudo.titulo
            if not self.conteudo_slug:
                self.conteudo_slug = self.conteudo.slug
            if not self.materia_nome:
                self.materia_nome = self.conteudo.materia.nome
        super().save(*args, **kwargs)


class TentativaSimulado(models.Model):
    class StatusTentativa(models.TextChoices):
        EM_ANDAMENTO = "in_progress", "Em andamento"
        FINALIZADA = "finished", "Finalizada"
        CANCELADA = "cancelled", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tentativas_simulados",
    )
    simulado = models.ForeignKey(
        Simulado,
        on_delete=models.PROTECT,
        related_name="tentativas",
    )
    iniciada_em = models.DateTimeField(auto_now_add=True)
    finalizada_em = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=StatusTentativa.choices,
        default=StatusTentativa.EM_ANDAMENTO,
    )
    total_questoes = models.PositiveSmallIntegerField(default=0)
    total_acertos = models.PositiveSmallIntegerField(default=0)
    percentual = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tempo_gasto = models.DurationField(null=True, blank=True)

    class Meta:
        ordering = ["-iniciada_em"]
        indexes = [
            models.Index(fields=["usuario", "-iniciada_em"]),
            models.Index(fields=["simulado", "-iniciada_em"]),
        ]
        verbose_name = "tentativa de simulado"
        verbose_name_plural = "tentativas de simulado"

    def __str__(self):
        return f"{self.usuario} - {self.simulado}"

    @property
    def finalizada(self):
        return self.status == self.StatusTentativa.FINALIZADA

    def finalizar(self):
        if self.finalizada:
            return
        respostas = list(self.respostas.select_related("alternativa_escolhida").all())
        total = self.simulado.questoes.count()
        acertos = sum(1 for resposta in respostas if resposta.correta)
        self.status = self.StatusTentativa.FINALIZADA
        self.finalizada_em = timezone.now()
        self.total_questoes = total
        self.total_acertos = acertos
        self.percentual = round((acertos / total) * 100, 2) if total else 0
        self.tempo_gasto = self.finalizada_em - self.iniciada_em
        self.save(
            update_fields=[
                "status",
                "finalizada_em",
                "total_questoes",
                "total_acertos",
                "percentual",
                "tempo_gasto",
            ]
        )


class RespostaSimulado(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tentativa = models.ForeignKey(
        TentativaSimulado,
        on_delete=models.CASCADE,
        related_name="respostas",
    )
    questao_simulado = models.ForeignKey(
        QuestaoSimulado,
        on_delete=models.PROTECT,
        related_name="respostas",
    )
    alternativa_escolhida = models.ForeignKey(
        AlternativaSimulado,
        on_delete=models.PROTECT,
        related_name="respostas",
    )
    alternativa_chave = models.CharField(max_length=4)
    alternativa_texto = models.TextField()
    correta = models.BooleanField(default=False)
    respondida_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["questao_simulado__ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["tentativa", "questao_simulado"],
                name="unique_resposta_por_questao_tentativa",
            ),
        ]
        verbose_name = "resposta de simulado"
        verbose_name_plural = "respostas de simulado"

    def clean(self):
        super().clean()
        if self.tentativa_id and self.questao_simulado_id:
            if self.questao_simulado.simulado_id != self.tentativa.simulado_id:
                raise ValidationError("A questão não pertence ao simulado da tentativa.")
        if self.questao_simulado_id and self.alternativa_escolhida_id:
            if self.alternativa_escolhida.questao_simulado_id != self.questao_simulado_id:
                raise ValidationError("A alternativa não pertence à questão.")
        if self.tentativa_id and self.tentativa.finalizada:
            raise ValidationError("Tentativa finalizada não pode ser alterada.")

    def save(self, *args, **kwargs):
        if self.tentativa_id and self.tentativa.finalizada:
            raise ValidationError("Tentativa finalizada não pode ser alterada.")
        if self.alternativa_escolhida_id:
            self.alternativa_chave = self.alternativa_escolhida.chave
            self.alternativa_texto = self.alternativa_escolhida.texto
            self.correta = self.alternativa_escolhida.correta
        super().save(*args, **kwargs)
