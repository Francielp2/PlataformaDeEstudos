import math
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from estudos.models import ConteudoEstudado

from .models import ProgressoVideo, SessaoVideo, VideoConteudo


PERCENTUAL_CONCLUSAO = 95
TAMANHO_BLOCO_SEGUNDOS = 5
MAXIMO_SEGMENTOS_POR_REQUISICAO = 2000
DURACAO_MAXIMA_SEGUNDOS = 21600
MAXIMO_SEGUNDOS_POR_REQUISICAO = 60
# Antifraude: o tempo creditado não cresce mais rápido que a reprodução em 2x
# desde o último registro, e o total de blocos de um aluno num vídeo não passa
# do tempo creditado (em blocos) mais uma folga fixa para as bordas dos trechos.
VELOCIDADE_MAXIMA = 2
FOLGA_BLOCOS = 4
# O player só retoma de onde o aluno parou se houver pelo menos isso de vídeo antes e depois.
MARGEM_INICIO_RETOMADA = 5
MARGEM_FIM_RETOMADA = 10


def aplicar_metadados(video, metadados):
    """Grava no vídeo os dados de autoria vindos do oEmbed do YouTube."""
    video.titulo = metadados["titulo"]
    video.canal_nome = metadados["canal_nome"]
    video.canal_url = metadados["canal_url"]
    video.thumbnail_url = metadados.get("thumbnail_url", "")
    video.metadados_atualizados_em = timezone.now()


def posicao_para_retomar(video, progresso):
    if not progresso or progresso.concluido or not video.duracao_segundos:
        return None
    posicao = progresso.ultima_posicao_segundos
    if MARGEM_INICIO_RETOMADA < posicao < video.duracao_segundos - MARGEM_FIM_RETOMADA:
        return posicao
    return None


def videos_do_conteudo_para_usuario(conteudo, usuario):
    """Vídeos ativos do conteúdo com o progresso do usuário (uma query para cada)."""
    videos = list(VideoConteudo.objects.filter(conteudo=conteudo, ativo=True).order_by("ordem", "criado_em"))
    progressos = {}
    if videos and usuario.is_authenticated:
        progressos = {
            progresso.video_id: progresso
            for progresso in ProgressoVideo.objects.filter(usuario=usuario, video__in=videos)
        }
    itens = []
    for video in videos:
        progresso = progressos.get(video.pk)
        itens.append(
            {
                "video": video,
                "progresso": progresso,
                "inicio": posicao_para_retomar(video, progresso),
            }
        )
    return itens


def _numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def validar_dados_progresso(dados):
    """Valida o corpo enviado pelo player. Lança ValidationError (resposta 400)."""
    if not isinstance(dados, dict):
        raise ValidationError("Corpo da requisição inválido.")
    try:
        sessao_id = uuid.UUID(str(dados.get("sessao_id")))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("sessao_id inválido.")

    segmentos = dados.get("segmentos", [])
    if not isinstance(segmentos, list) or len(segmentos) > MAXIMO_SEGMENTOS_POR_REQUISICAO:
        raise ValidationError("segmentos deve ser uma lista de inteiros.")
    if any(not isinstance(item, int) or isinstance(item, bool) for item in segmentos):
        raise ValidationError("segmentos deve ser uma lista de inteiros.")

    posicao = dados.get("posicao", 0)
    if not _numero(posicao) or posicao < 0:
        raise ValidationError("posicao inválida.")

    duracao = dados.get("duracao")
    if not _numero(duracao) or not 0 < duracao <= DURACAO_MAXIMA_SEGUNDOS:
        raise ValidationError("duracao inválida.")

    segundos = dados.get("segundos_assistidos", 0)
    if not _numero(segundos):
        raise ValidationError("segundos_assistidos inválido.")

    return {
        "sessao_id": sessao_id,
        "segmentos": segmentos,
        "posicao": int(posicao),
        "duracao": duracao,
        "segundos_assistidos": int(min(max(segundos, 0), MAXIMO_SEGUNDOS_POR_REQUISICAO)),
    }


def _percentual(blocos, total_blocos):
    valor = min(100, len(blocos) / total_blocos * 100)
    return Decimal(str(round(valor, 2)))


def _total_blocos(duracao):
    return math.ceil(duracao / TAMANHO_BLOCO_SEGUNDOS)


def _credito_de_segundos(progresso, criado, agora):
    """Segundos que podem ser creditados agora, pelo tempo real desde o último registro."""
    decorrido = 0 if criado else max(0, (agora - progresso.atualizado_em).total_seconds())
    return int(min(MAXIMO_SEGUNDOS_POR_REQUISICAO, decorrido * VELOCIDADE_MAXIMA))


def _limitar_blocos_novos(blocos_recebidos, blocos_ja_assistidos, segundos_total):
    """Aceita só os blocos novos que cabem no tempo total já creditado ao aluno."""
    limite = math.ceil(segundos_total / TAMANHO_BLOCO_SEGUNDOS) + FOLGA_BLOCOS
    vagas = max(0, limite - len(blocos_ja_assistidos))
    novos = sorted(blocos_recebidos - blocos_ja_assistidos)
    return set(novos[:vagas])


def recalcular_percentuais(video):
    """Recalcula o percentual de todos os alunos depois que a duração do vídeo muda.

    Não altera `concluido` nem as marcações de estudado já feitas.
    """
    if not video.duracao_segundos:
        return 0
    total_blocos = _total_blocos(video.duracao_segundos)
    progressos = list(ProgressoVideo.objects.filter(video=video))
    for progresso in progressos:
        blocos = [bloco for bloco in progresso.segmentos_assistidos if 0 <= bloco < total_blocos]
        progresso.segmentos_assistidos = blocos
        progresso.percentual = _percentual(blocos, total_blocos)
    ProgressoVideo.objects.bulk_update(progressos, ["segmentos_assistidos", "percentual"])
    return len(progressos)


def registrar_progresso(video, usuario, dados):
    """Consolida o progresso e a sessão do aluno. `dados` vem de validar_dados_progresso."""
    with transaction.atomic():
        video = VideoConteudo.objects.select_for_update().get(pk=video.pk)
        if not video.duracao_segundos:
            video.duracao_segundos = max(1, round(dados["duracao"]))
            video.save(update_fields=["duracao_segundos", "atualizado_em"])
        duracao = video.duracao_segundos
        total_blocos = _total_blocos(duracao)
        posicao = min(dados["posicao"], duracao)

        agora = timezone.now()
        progresso, criado = ProgressoVideo.objects.select_for_update().get_or_create(usuario=usuario, video=video)
        ja_assistidos = set(progresso.segmentos_assistidos)
        segundos = min(dados["segundos_assistidos"], _credito_de_segundos(progresso, criado, agora))
        blocos_recebidos = {bloco for bloco in dados["segmentos"] if 0 <= bloco < total_blocos}
        blocos_recebidos = (blocos_recebidos & ja_assistidos) | _limitar_blocos_novos(
            blocos_recebidos, ja_assistidos, progresso.segundos_assistidos_total + segundos
        )
        blocos = ja_assistidos | blocos_recebidos
        progresso.segmentos_assistidos = sorted(blocos)
        progresso.percentual = _percentual(blocos, total_blocos)
        progresso.ultima_posicao_segundos = posicao
        progresso.segundos_assistidos_total += segundos

        inicio_recebido = min(blocos_recebidos) * TAMANHO_BLOCO_SEGUNDOS if blocos_recebidos else posicao
        sessao, criada = SessaoVideo.objects.select_for_update().get_or_create(
            pk=dados["sessao_id"],
            defaults={
                "usuario": usuario,
                "video": video,
                "inicio_segundos": inicio_recebido,
                "fim_segundos": posicao,
                "segundos_assistidos": 0,
                "percentual_video": progresso.percentual,
            },
        )
        if sessao.usuario_id != usuario.pk or sessao.video_id != video.pk:
            raise ValidationError("Sessão de vídeo inválida.")
        if not criada:
            sessao.inicio_segundos = min(sessao.inicio_segundos, inicio_recebido)
            sessao.fim_segundos = max(sessao.fim_segundos, posicao)
        sessao.segundos_assistidos += segundos
        sessao.percentual_video = progresso.percentual
        sessao.full_clean()
        sessao.save()

        marcou_estudado = False
        if progresso.percentual >= PERCENTUAL_CONCLUSAO and not progresso.concluido:
            progresso.concluido = True
            progresso.concluido_em = timezone.now()
            _, marcou_estudado = ConteudoEstudado.objects.get_or_create(
                usuario=usuario,
                conteudo=video.conteudo,
            )
            if marcou_estudado:
                progresso.marcou_conteudo_estudado = True
        progresso.full_clean()
        progresso.save()

    return {
        "percentual": float(progresso.percentual),
        "concluido": progresso.concluido,
        "marcou_estudado": marcou_estudado,
        "ultima_posicao": progresso.ultima_posicao_segundos,
    }
