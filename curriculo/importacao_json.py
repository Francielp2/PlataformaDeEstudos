import json

from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import IntegrityError, transaction

from .models import Conteudo, Materia


def _json_payload(texto):
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            [f"O JSON informado é inválido. Linha {exc.lineno}, coluna {exc.colno}: {exc.msg}."]
        )


def _validar_ordem(valor, prefixo, campo, erros):
    if not isinstance(valor, int) or valor < 0:
        erros.append(f"{prefixo} {campo} deve ser um número inteiro maior ou igual a zero.")


def validar_json_importacao_materias(texto):
    payload = _json_payload(texto)
    if not isinstance(payload, dict) or not isinstance(payload.get("materias"), list):
        raise ValidationError(['Campo "materias" deve ser uma lista.'])
    if not payload["materias"]:
        raise ValidationError(['Campo "materias" não pode ser vazio.'])

    nomes = set()
    slugs = set()
    erros = []
    validadas = []

    for indice, item in enumerate(payload["materias"], start=1):
        prefixo = f"Item {indice}:"
        if not isinstance(item, dict):
            erros.append(f"{prefixo} item inválido.")
            continue

        nome = " ".join((item.get("nome") or "").split())
        slug = (item.get("slug") or "").strip()
        descricao = item.get("descricao", "")
        ordem = item.get("ordem_exibicao", 0)
        ativa = item.get("ativa", True)

        if not nome:
            erros.append(f"{prefixo} nome é obrigatório.")
        elif nome.lower() in nomes or Materia.objects.filter(nome__iexact=nome).exists():
            erros.append(f'{prefixo} nome "{nome}" já existe.')
        nomes.add(nome.lower())

        if not slug:
            erros.append(f"{prefixo} slug é obrigatório.")
        else:
            try:
                validate_slug(slug)
            except ValidationError:
                erros.append(f'{prefixo} slug "{slug}" inválido.')
            if slug in slugs or Materia.objects.filter(slug=slug).exists():
                erros.append(f'{prefixo} slug "{slug}" já existe.')
            slugs.add(slug)

        _validar_ordem(ordem, prefixo, "ordem_exibicao", erros)
        if not isinstance(ativa, bool):
            erros.append(f"{prefixo} ativa deve ser booleano.")
        if not isinstance(descricao, str):
            erros.append(f"{prefixo} descricao deve ser texto.")

        materia = Materia(
            nome=nome,
            slug=slug,
            descricao=descricao if isinstance(descricao, str) else "",
            ordem_exibicao=ordem if isinstance(ordem, int) else 0,
            ativa=ativa if isinstance(ativa, bool) else True,
        )
        try:
            materia.full_clean()
        except ValidationError as exc:
            for mensagens in exc.message_dict.values():
                erros.extend(f"{prefixo} {mensagem}" for mensagem in mensagens)
        validadas.append(materia)

    if erros:
        raise ValidationError(erros)
    return validadas


def importar_materias_json(texto, usuario):
    materias = validar_json_importacao_materias(texto)
    try:
        with transaction.atomic():
            for materia in materias:
                materia.criado_por = usuario
                materia.full_clean()
                materia.save()
    except IntegrityError as exc:
        raise ValidationError("Não foi possível importar o JSON. Verifique duplicidades.") from exc
    return materias


def validar_json_importacao_conteudos(texto):
    payload = _json_payload(texto)
    if not isinstance(payload, dict) or not isinstance(payload.get("conteudos"), list):
        raise ValidationError(['Campo "conteudos" deve ser uma lista.'])
    if not payload["conteudos"]:
        raise ValidationError(['Campo "conteudos" não pode ser vazio.'])

    dificuldades = {choice.value for choice in Conteudo.DificuldadeConteudo}
    status_validos = {choice.value for choice in Conteudo.StatusConteudo}
    materia_padrao = payload.get("materia") if isinstance(payload.get("materia"), str) else ""
    chaves = set()
    erros = []
    validadas = []
    materias_por_slug = {materia.slug: materia for materia in Materia.objects.all()}
    existentes = {
        (conteudo.materia.slug, conteudo.slug): conteudo
        for conteudo in Conteudo.objects.select_related("materia")
    }
    existentes_por_slug = {}
    for conteudo in Conteudo.objects.select_related("materia"):
        existentes_por_slug.setdefault(conteudo.slug, []).append(conteudo)

    for indice, item in enumerate(payload["conteudos"], start=1):
        prefixo = f"Conteúdo {indice}:"
        if not isinstance(item, dict):
            erros.append(f"{prefixo} item inválido.")
            continue

        materia_slug = (item.get("materia") or materia_padrao or "").strip()
        materia = materias_por_slug.get(materia_slug)
        titulo = " ".join((item.get("titulo") or "").split())
        slug = (item.get("slug") or "").strip()
        resumo = item.get("resumo", "")
        texto_estudo = item.get("texto_estudo", "")
        dificuldade = item.get("dificuldade") or Conteudo.DificuldadeConteudo.BASICO
        status = item.get("status") or Conteudo.StatusConteudo.RASCUNHO
        ordem = item.get("ordem_sugerida", 0)
        pai_slug = item.get("pai")

        if not materia_slug:
            erros.append(f"{prefixo} matéria é obrigatória.")
        elif not materia:
            erros.append(f'{prefixo} matéria "{materia_slug}" não encontrada.')
        if not titulo:
            erros.append(f"{prefixo} título é obrigatório.")
        if not slug:
            erros.append(f"{prefixo} slug é obrigatório.")
        else:
            try:
                validate_slug(slug)
            except ValidationError:
                erros.append(f'{prefixo} slug "{slug}" inválido.')
        if not isinstance(resumo, str) or not resumo.strip():
            erros.append(f"{prefixo} resumo é obrigatório.")
        if not isinstance(texto_estudo, str):
            erros.append(f"{prefixo} texto_estudo deve ser texto.")
        if dificuldade not in dificuldades:
            erros.append(f'{prefixo} dificuldade "{dificuldade}" inválida.')
        if status not in status_validos:
            erros.append(f'{prefixo} status "{status}" inválido.')
        _validar_ordem(ordem, prefixo, "ordem_sugerida", erros)
        if pai_slug is not None and not isinstance(pai_slug, str):
            erros.append(f"{prefixo} pai deve ser nulo ou slug.")

        chave = (materia_slug, slug)
        if materia and slug:
            if chave in chaves or chave in existentes:
                erros.append(f'{prefixo} slug "{slug}" já existe para a matéria "{materia_slug}".')
            chaves.add(chave)
        if pai_slug and pai_slug == slug:
            erros.append(f"{prefixo} conteúdo não pode ser pai de si mesmo.")

        conteudo = Conteudo(
            materia=materia,
            titulo=titulo,
            slug=slug,
            resumo=resumo if isinstance(resumo, str) else "",
            texto_estudo=texto_estudo if isinstance(texto_estudo, str) else "",
            dificuldade=dificuldade,
            status=status,
            ordem_sugerida=ordem if isinstance(ordem, int) else 0,
            pai=None,
        )
        try:
            conteudo.full_clean()
        except ValidationError as exc:
            for mensagens in exc.message_dict.values():
                erros.extend(f"{prefixo} {mensagem}" for mensagem in mensagens)
        validadas.append(
            {
                "indice": indice,
                "materia_slug": materia_slug,
                "slug": slug,
                "pai_slug": pai_slug,
                "conteudo": conteudo,
            }
        )

    importados_por_chave = {
        (item["materia_slug"], item["slug"]): item
        for item in validadas
        if item["materia_slug"] and item["slug"]
    }

    for item in validadas:
        pai_slug = item["pai_slug"]
        if not pai_slug:
            continue
        prefixo = f"Conteúdo {item['indice']}:"
        chave_pai = (item["materia_slug"], pai_slug)
        pai_existente = existentes.get(chave_pai)
        pai_importado = importados_por_chave.get(chave_pai)
        if not pai_existente and not pai_importado:
            if pai_slug in existentes_por_slug:
                erros.append(
                    f'{prefixo} conteúdo pai "{pai_slug}" não pertence à matéria "{item["materia_slug"]}".'
                )
            else:
                erros.append(f'{prefixo} conteúdo pai "{pai_slug}" não encontrado.')

    for item in validadas:
        visitados = set()
        atual = item
        while atual and atual["pai_slug"]:
            chave_atual = (atual["materia_slug"], atual["slug"])
            chave_pai = (atual["materia_slug"], atual["pai_slug"])
            if chave_pai in visitados or chave_pai == chave_atual:
                erros.append(f"Conteúdo {item['indice']}: a hierarquia de conteúdos não pode formar ciclos.")
                break
            visitados.add(chave_atual)
            atual = importados_por_chave.get(chave_pai)

    if erros:
        raise ValidationError(erros)
    return validadas, existentes


def importar_conteudos_json(texto, usuario):
    validadas, existentes = validar_json_importacao_conteudos(texto)
    criados = {}
    try:
        with transaction.atomic():
            for item in validadas:
                conteudo = item["conteudo"]
                conteudo.criado_por = usuario
                conteudo.full_clean()
                conteudo.save()
                criados[(item["materia_slug"], item["slug"])] = conteudo

            for item in validadas:
                pai_slug = item["pai_slug"]
                if not pai_slug:
                    continue
                conteudo = criados[(item["materia_slug"], item["slug"])]
                pai = criados.get((item["materia_slug"], pai_slug)) or existentes[
                    (item["materia_slug"], pai_slug)
                ]
                conteudo.pai = pai
                conteudo.full_clean()
                conteudo.save(update_fields=["pai", "atualizado_em"])
    except IntegrityError as exc:
        raise ValidationError("Não foi possível importar o JSON. Verifique duplicidades.") from exc
    return list(criados.values())
