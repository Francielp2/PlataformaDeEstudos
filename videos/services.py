import math
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import ProgressoVideo, SessaoVideo, VideoConteudo


# Limite de posição aceita: 6 horas.
POSICAO_MAXIMA_SEGUNDOS = 21600
MAXIMO_SEGUNDOS_POR_REQUISICAO = 60
# Antifraude: o tempo assistido creditado não cresce mais rápido que a reprodução
# em 2x desde o último registro do aluno naquele vídeo.
VELOCIDADE_MAXIMA = 2
# O player só retoma de onde o aluno parou depois dos primeiros segundos do vídeo.
MARGEM_INICIO_RETOMADA = 5


def aplicar_metadados(video, metadados):
    """Grava no vídeo os dados de autoria vindos do oEmbed do YouTube."""
    video.titulo = metadados["titulo"]
    video.canal_nome = metadados["canal_nome"]
    video.canal_url = metadados["canal_url"]
    video.thumbnail_url = metadados.get("thumbnail_url", "")
    video.metadados_atualizados_em = timezone.now()


def posicao_para_retomar(progresso):
    if progresso and progresso.ultima_posicao_segundos > MARGEM_INICIO_RETOMADA:
        return progresso.ultima_posicao_segundos
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
                "inicio": posicao_para_retomar(progresso),
            }
        )
    return itens


def _numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _posicao(dados, campo):
    valor = dados.get(campo, 0)
    if not _numero(valor) or not 0 <= valor <= POSICAO_MAXIMA_SEGUNDOS:
        raise ValidationError(f"{campo} inválido.")
    return int(valor)


def validar_dados_progresso(dados):
    """Valida o corpo enviado pelo player. Lança ValidationError (resposta 400)."""
    if not isinstance(dados, dict):
        raise ValidationError("Corpo da requisição inválido.")
    try:
        sessao_id = uuid.UUID(str(dados.get("sessao_id")))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("sessao_id inválido.")

    posicao = _posicao(dados, "posicao")
    inicio = _posicao(dados, "inicio") if "inicio" in dados else posicao
    if inicio > posicao:
        raise ValidationError("inicio não pode ser maior que posicao.")

    segundos = dados.get("segundos_assistidos", 0)
    if not _numero(segundos):
        raise ValidationError("segundos_assistidos inválido.")

    terminou = dados.get("terminou", False)
    if not isinstance(terminou, bool):
        raise ValidationError("terminou deve ser booleano.")

    return {
        "sessao_id": sessao_id,
        "inicio": inicio,
        "posicao": posicao,
        "segundos_assistidos": int(min(max(segundos, 0), MAXIMO_SEGUNDOS_POR_REQUISICAO)),
        "terminou": terminou,
    }


def _credito_de_segundos(progresso, criado, agora):
    """Segundos que podem ser creditados agora, pelo tempo real desde o último registro."""
    decorrido = 0 if criado else max(0, (agora - progresso.atualizado_em).total_seconds())
    return int(min(MAXIMO_SEGUNDOS_POR_REQUISICAO, decorrido * VELOCIDADE_MAXIMA))


def registrar_progresso(video, usuario, dados):
    """Registra a posição e o tempo assistido. `dados` vem de validar_dados_progresso.

    Assistir ao vídeo não marca o conteúdo como estudado: essa marcação é manual.
    """
    with transaction.atomic():
        agora = timezone.now()
        progresso, criado = ProgressoVideo.objects.select_for_update().get_or_create(usuario=usuario, video=video)
        segundos = min(dados["segundos_assistidos"], _credito_de_segundos(progresso, criado, agora))
        # Ao terminar o vídeo, a próxima vez começa do início.
        progresso.ultima_posicao_segundos = 0 if dados["terminou"] else dados["posicao"]
        progresso.segundos_assistidos_total += segundos

        sessao, criada = SessaoVideo.objects.select_for_update().get_or_create(
            pk=dados["sessao_id"],
            defaults={
                "usuario": usuario,
                "video": video,
                "inicio_segundos": dados["inicio"],
                "fim_segundos": dados["posicao"],
                "segundos_assistidos": 0,
            },
        )
        if sessao.usuario_id != usuario.pk or sessao.video_id != video.pk:
            raise ValidationError("Sessão de vídeo inválida.")
        if not criada:
            sessao.inicio_segundos = min(sessao.inicio_segundos, dados["inicio"])
            sessao.fim_segundos = max(sessao.fim_segundos, dados["posicao"])
        sessao.segundos_assistidos += segundos
        sessao.full_clean()
        sessao.save()

        progresso.full_clean()
        progresso.save()

    return {"ultima_posicao": progresso.ultima_posicao_segundos}
