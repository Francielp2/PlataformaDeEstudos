import json
from concurrent.futures import ThreadPoolExecutor

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from curriculo.models import Conteudo, Materia

from . import youtube
from .models import VideoConteudo
from .services import aplicar_metadados


MAXIMO_VIDEOS_POR_IMPORTACAO = 50
CONSULTAS_SIMULTANEAS = 8


def _json_payload(texto):
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            [f"O JSON informado é inválido. Linha {exc.lineno}, coluna {exc.colno}: {exc.msg}."]
        )


def _youtube_id_do_item(item, prefixo, erros):
    url = item.get("url")
    youtube_id = item.get("youtube_id")
    if url in (None, "") and youtube_id in (None, ""):
        erros.append(f"{prefixo} informe url ou youtube_id.")
        return None
    ids = []
    for campo, valor in (("url", url), ("youtube_id", youtube_id)):
        if valor in (None, ""):
            continue
        if not isinstance(valor, str):
            erros.append(f"{prefixo} {campo} deve ser texto.")
            return None
        try:
            ids.append(youtube.extrair_youtube_id(valor))
        except ValidationError:
            erros.append(f"{prefixo} {campo} não é um link ou identificador do YouTube válido.")
            return None
    if len(set(ids)) > 1:
        erros.append(f"{prefixo} url e youtube_id apontam para vídeos diferentes.")
        return None
    return ids[0]


def validar_json_importacao_videos(texto):
    """Fase 1: valida todos os itens localmente, sem acessar a rede."""
    payload = _json_payload(texto)
    if not isinstance(payload, dict) or not isinstance(payload.get("videos"), list):
        raise ValidationError(['Campo "videos" deve ser uma lista.'])
    if not payload["videos"]:
        raise ValidationError(['Campo "videos" não pode ser vazio.'])
    if len(payload["videos"]) > MAXIMO_VIDEOS_POR_IMPORTACAO:
        raise ValidationError(
            [f'Campo "videos" aceita no máximo {MAXIMO_VIDEOS_POR_IMPORTACAO} itens por importação.']
        )

    materia_padrao = payload.get("materia") if isinstance(payload.get("materia"), str) else ""
    materias_por_slug = {materia.slug: materia for materia in Materia.objects.all()}
    conteudos = list(Conteudo.objects.select_related("materia"))
    conteudos_por_chave = {(conteudo.materia.slug, conteudo.slug): conteudo for conteudo in conteudos}
    slugs_conteudo = {conteudo.slug for conteudo in conteudos}
    existentes = set(VideoConteudo.objects.values_list("conteudo_id", "youtube_id"))
    chaves = set()
    erros = []
    validados = []

    for indice, item in enumerate(payload["videos"], start=1):
        prefixo = f"Vídeo {indice}:"
        if not isinstance(item, dict):
            erros.append(f"{prefixo} item inválido.")
            continue

        materia_slug = item.get("materia") or materia_padrao or ""
        conteudo_slug = item.get("conteudo") or ""
        nota_curador = item.get("nota_curador", "")
        ordem = item.get("ordem", 0)
        ativo = item.get("ativo", True)

        materia = None
        if not isinstance(materia_slug, str) or not materia_slug.strip():
            erros.append(f"{prefixo} matéria é obrigatória.")
        else:
            materia_slug = materia_slug.strip()
            materia = materias_por_slug.get(materia_slug)
            if not materia:
                erros.append(f'{prefixo} matéria "{materia_slug}" não encontrada.')

        conteudo = None
        if not isinstance(conteudo_slug, str) or not conteudo_slug.strip():
            erros.append(f"{prefixo} conteúdo é obrigatório.")
        elif materia:
            conteudo_slug = conteudo_slug.strip()
            conteudo = conteudos_por_chave.get((materia_slug, conteudo_slug))
            if not conteudo:
                if conteudo_slug in slugs_conteudo:
                    erros.append(f'{prefixo} conteúdo "{conteudo_slug}" não pertence à matéria "{materia_slug}".')
                else:
                    erros.append(f'{prefixo} conteúdo "{conteudo_slug}" não encontrado.')

        youtube_id = _youtube_id_do_item(item, prefixo, erros)

        if not isinstance(nota_curador, str):
            erros.append(f"{prefixo} nota_curador deve ser texto.")
        if not isinstance(ordem, int) or isinstance(ordem, bool) or ordem < 0:
            erros.append(f"{prefixo} ordem deve ser um número inteiro maior ou igual a zero.")
        elif ordem > 32767:
            erros.append(f"{prefixo} ordem deve ser no máximo 32767.")
        if not isinstance(ativo, bool):
            erros.append(f"{prefixo} ativo deve ser booleano.")

        if conteudo and youtube_id:
            chave = (conteudo.pk, youtube_id)
            if chave in chaves:
                erros.append(f'{prefixo} o vídeo "{youtube_id}" está repetido para o conteúdo "{conteudo_slug}" neste JSON.')
            elif chave in existentes:
                erros.append(f'{prefixo} o vídeo "{youtube_id}" já está cadastrado no conteúdo "{conteudo_slug}".')
            chaves.add(chave)

        # titulo, canal, canal_nome e canal_url são ignorados: a autoria sempre vem do YouTube.
        validados.append(
            {
                "indice": indice,
                "youtube_id": youtube_id,
                "video": VideoConteudo(
                    conteudo=conteudo,
                    youtube_id=youtube_id or "",
                    nota_curador=nota_curador if isinstance(nota_curador, str) else "",
                    ordem=ordem if isinstance(ordem, int) and not isinstance(ordem, bool) and ordem >= 0 else 0,
                    ativo=ativo if isinstance(ativo, bool) else True,
                ),
            }
        )

    if erros:
        raise ValidationError(erros)
    return validados


def _buscar_metadados(youtube_id):
    try:
        return youtube_id, youtube.buscar_metadados_youtube(youtube_id), None
    except ValidationError as exc:
        return youtube_id, None, exc.messages[0]


def buscar_metadados_em_paralelo(youtube_ids):
    """Fase 2: consulta o oEmbed uma vez por vídeo, em paralelo."""
    with ThreadPoolExecutor(max_workers=CONSULTAS_SIMULTANEAS) as executor:
        resultados = executor.map(_buscar_metadados, sorted(set(youtube_ids)))
        return {youtube_id: (metadados, erro) for youtube_id, metadados, erro in resultados}


def importar_videos_json(texto, usuario):
    validados = validar_json_importacao_videos(texto)

    resultados = buscar_metadados_em_paralelo(item["youtube_id"] for item in validados)
    erros = []
    for item in validados:
        metadados, erro = resultados[item["youtube_id"]]
        if erro:
            erros.append(f"Vídeo {item['indice']}: {erro}")
        else:
            aplicar_metadados(item["video"], metadados)
    if erros:
        raise ValidationError(erros)

    try:
        with transaction.atomic():
            for item in validados:
                video = item["video"]
                video.criado_por = usuario
                try:
                    video.full_clean()
                except ValidationError as exc:
                    erros.extend(f"Vídeo {item['indice']}: {mensagem}" for mensagem in exc.messages)
                    continue
                video.save()
            if erros:
                raise ValidationError(erros)
    except IntegrityError as exc:
        raise ValidationError("Não foi possível importar o JSON. Verifique duplicidades.") from exc
    return [item["video"] for item in validados]
