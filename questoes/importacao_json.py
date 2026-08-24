import json

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from curriculo.models import Conteudo, Materia

from .models import Alternativa, Questao, QuestaoConteudo


CHAVES_VALIDAS = {chr(codigo) for codigo in range(ord("A"), ord("Z") + 1)}


def _normalizar_codigo(codigo):
    return " ".join((codigo or "").split()).upper()


def validar_json_importacao_questoes(texto):
    try:
        payload = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            [f"O JSON informado é inválido. Linha {exc.lineno}, coluna {exc.colno}: {exc.msg}."]
        )

    if not isinstance(payload, dict) or not isinstance(payload.get("questoes"), list):
        raise ValidationError(['Campo "questoes" deve ser uma lista.'])
    if not payload["questoes"]:
        raise ValidationError(['Campo "questoes" não pode ser vazio.'])

    dificuldades = {choice.value for choice in Questao.DificuldadeQuestao}
    fontes = {choice.value for choice in Questao.TipoFonte}
    status_validos = {choice.value for choice in Questao.StatusQuestao}
    materia_padrao = payload.get("materia")
    codigos = set()
    erros = []
    validadas = []

    for indice, item in enumerate(payload["questoes"], start=1):
        prefixo = f"Questão {indice}:"
        if not isinstance(item, dict):
            erros.append(f"{prefixo} item inválido.")
            continue

        codigo = _normalizar_codigo(item.get("codigo"))
        enunciado = (item.get("enunciado") or "").strip()
        materia_slug = item.get("materia") or materia_padrao
        dificuldade = item.get("dificuldade") or Questao.DificuldadeQuestao.MEDIA
        tipo_fonte = item.get("tipo_fonte") or Questao.TipoFonte.ORIGINAL
        status = item.get("status") or Questao.StatusQuestao.RASCUNHO
        alternativas = item.get("alternativas")
        conteudo_slugs = item.get("conteudos") or []
        principal_slug = item.get("conteudo_principal")
        gabarito = _normalizar_codigo(item.get("gabarito")) if item.get("gabarito") else ""

        if item.get("requer_imagem") is True:
            erros.append(
                f"{prefixo} requer imagem, mas o suporte a imagens ainda não está disponível."
            )
        if not codigo:
            erros.append(f"{prefixo} código é obrigatório.")
        elif codigo in codigos or Questao.objects.filter(codigo=codigo).exists():
            erros.append(f'Questão {codigo} já existe.')
        codigos.add(codigo)
        if not enunciado:
            erros.append(f"{prefixo} enunciado é obrigatório.")
        if not materia_slug:
            erros.append(f"{prefixo} matéria é obrigatória.")
        if dificuldade not in dificuldades:
            erros.append(f'{prefixo} dificuldade "{dificuldade}" inválida.')
        if tipo_fonte not in fontes:
            erros.append(f'{prefixo} fonte "{tipo_fonte}" inválida.')
        if status not in status_validos:
            erros.append(f'{prefixo} status "{status}" inválido.')
        if not isinstance(conteudo_slugs, list) or not conteudo_slugs:
            erros.append(f"{prefixo} informe pelo menos 1 conteúdo.")
            conteudo_slugs = []
        if principal_slug not in conteudo_slugs:
            erros.append(
                f"{prefixo} o conteúdo principal não pertence aos conteúdos selecionados."
            )
        if not isinstance(alternativas, list) or len(alternativas) < 2:
            erros.append(f"{prefixo} informe pelo menos 2 alternativas.")
            alternativas = []

        materia = None
        if materia_slug:
            materia = Materia.objects.filter(slug=materia_slug).first()
            if not materia:
                erros.append(f'{prefixo} matéria "{materia_slug}" não encontrada.')

        conteudos = []
        for slug in conteudo_slugs:
            conteudo = Conteudo.objects.select_related("materia").filter(slug=slug).first()
            if not conteudo:
                erros.append(f'{prefixo} conteúdo "{slug}" não encontrado.')
            else:
                conteudos.append(conteudo)
                if materia and conteudo.materia_id != materia.id:
                    erros.append(
                        f'{prefixo} conteúdo "{slug}" não pertence à matéria "{materia.slug}".'
                    )
        principal = next((conteudo for conteudo in conteudos if conteudo.slug == principal_slug), None)

        alternativas_validadas = []
        chaves = set()
        corretas = []
        ordens = set()
        for alt_indice, alternativa in enumerate(alternativas, start=1):
            if not isinstance(alternativa, dict):
                erros.append(f"{prefixo} alternativa {alt_indice} inválida.")
                continue
            chave = _normalizar_codigo(alternativa.get("chave"))
            texto_alt = (alternativa.get("texto") or "").strip()
            correta = bool(alternativa.get("correta"))
            ordem = alternativa.get("ordem") or alt_indice
            if chave not in CHAVES_VALIDAS:
                erros.append(f"{prefixo} alternativa {alt_indice} possui chave inválida.")
            if chave in chaves:
                erros.append(f"{prefixo} alternativa {chave} duplicada.")
            if not texto_alt:
                erros.append(f"{prefixo} alternativa {chave or alt_indice} sem texto.")
            if not isinstance(ordem, int) or ordem < 1:
                erros.append(f"{prefixo} alternativa {chave or alt_indice} possui ordem inválida.")
            elif ordem in ordens:
                erros.append(f"{prefixo} ordem {ordem} duplicada nas alternativas.")
            chaves.add(chave)
            ordens.add(ordem)
            if correta:
                corretas.append(chave)
            alternativas_validadas.append(
                {"chave": chave, "texto": texto_alt, "correta": correta, "ordem": ordem}
            )

        if len(corretas) == 0:
            erros.append(f"{prefixo} nenhuma alternativa foi marcada como correta.")
        elif len(corretas) > 1:
            erros.append(f"{prefixo} existem duas alternativas marcadas como corretas.")
        if gabarito and corretas and gabarito != corretas[0]:
            erros.append(
                f'{prefixo} gabarito "{gabarito}" diverge da alternativa marcada como correta.'
            )

        validadas.append(
            {
                "codigo": codigo,
                "materia": materia,
                "enunciado": enunciado,
                "explicacao": item.get("explicacao", ""),
                "dificuldade": dificuldade,
                "tipo_fonte": tipo_fonte,
                "fonte_nome": item.get("fonte_nome", ""),
                "fonte_ano": item.get("fonte_ano"),
                "fonte_url": item.get("fonte_url", ""),
                "status": status,
                "conteudos": conteudos,
                "principal": principal,
                "alternativas": alternativas_validadas,
            }
        )

    if erros:
        raise ValidationError(erros)
    return validadas


def importar_questoes_json(texto, usuario):
    questoes_validadas = validar_json_importacao_questoes(texto)
    criadas = []
    try:
        with transaction.atomic():
            for item in questoes_validadas:
                questao = Questao(
                    codigo=item["codigo"],
                    materia=item["materia"],
                    enunciado=item["enunciado"],
                    explicacao=item["explicacao"],
                    dificuldade=item["dificuldade"],
                    tipo_fonte=item["tipo_fonte"],
                    fonte_nome=item["fonte_nome"],
                    fonte_ano=item["fonte_ano"],
                    fonte_url=item["fonte_url"],
                    status=item["status"],
                    criado_por=usuario,
                )
                questao.full_clean()
                questao.save()
                for alternativa in item["alternativas"]:
                    alternativa_obj = Alternativa(questao=questao, **alternativa)
                    alternativa_obj.full_clean()
                    alternativa_obj.save()
                for conteudo in item["conteudos"]:
                    relacao = QuestaoConteudo(
                        questao=questao,
                        conteudo=conteudo,
                        principal=conteudo == item["principal"],
                    )
                    relacao.full_clean()
                    relacao.save()
                if questao.status == Questao.StatusQuestao.PUBLICADA:
                    questao.validar_publicacao()
                criadas.append(questao)
    except IntegrityError as exc:
        raise ValidationError("Não foi possível importar o JSON. Verifique duplicidades.") from exc
    return criadas
