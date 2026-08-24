import json
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from curriculo.models import Conteudo
from questoes.models import Alternativa, Questao, QuestaoConteudo

from .models import (
    AlternativaSimulado,
    QuestaoSimulado,
    QuestaoSimuladoConteudo,
    Simulado,
)


CHAVES_VALIDAS = {chr(codigo) for codigo in range(ord("A"), ord("Z") + 1)}


def proxima_ordem(simulado):
    ultima = simulado.questoes.order_by("-ordem").first()
    return (ultima.ordem + 1) if ultima else 1


def garantir_edicao_estrutural(simulado):
    if simulado.tentativas.exists():
        raise ValidationError(
            "Este simulado já possui tentativas e não permite alteração estrutural. Duplique para criar uma nova versão."
        )


def validar_materia_simulado(simulado, conteudos):
    if simulado.tipo == Simulado.TipoSimulado.POR_MATERIA:
        invalidos = [conteudo for conteudo in conteudos if conteudo.materia_id != simulado.materia_id]
        if invalidos:
            raise ValidationError(
                "Simulado por matéria só aceita conteúdos da matéria selecionada."
            )


def criar_snapshot_de_questao(simulado, questao, origem=QuestaoSimulado.OrigemQuestao.BANCO):
    garantir_edicao_estrutural(simulado)
    relacoes = list(questao.questao_conteudos.select_related("conteudo", "conteudo__materia"))
    conteudos = [relacao.conteudo for relacao in relacoes]
    validar_materia_simulado(simulado, conteudos)
    with transaction.atomic():
        snapshot = QuestaoSimulado.objects.create(
            simulado=simulado,
            questao_origem=questao,
            origem=origem,
            codigo_origem=questao.codigo,
            enunciado=questao.enunciado,
            explicacao=questao.explicacao,
            dificuldade=questao.dificuldade,
            tipo_fonte=questao.tipo_fonte,
            fonte_nome=questao.fonte_nome,
            fonte_ano=questao.fonte_ano,
            fonte_url=questao.fonte_url,
            ordem=proxima_ordem(simulado),
        )
        for alternativa in questao.alternativas.order_by("ordem"):
            AlternativaSimulado.objects.create(
                questao_simulado=snapshot,
                chave=alternativa.chave,
                texto=alternativa.texto,
                correta=alternativa.correta,
                ordem=alternativa.ordem,
            )
        for relacao in relacoes:
            QuestaoSimuladoConteudo.objects.create(
                questao_simulado=snapshot,
                conteudo=relacao.conteudo,
                principal=relacao.principal,
            )
    return snapshot


def criar_questao_banco_de_snapshot(dados, materia, conteudos, principal, usuario):
    if Questao.objects.filter(codigo=dados["codigo"]).exists():
        raise ValidationError(f'Já existe uma questão com o código "{dados["codigo"]}".')
    questao = Questao.objects.create(
        codigo=dados["codigo"],
        materia=materia,
        enunciado=dados["enunciado"],
        explicacao=dados.get("explicacao", ""),
        dificuldade=dados.get("dificuldade", Questao.DificuldadeQuestao.MEDIA),
        tipo_fonte=dados.get("tipo_fonte", Questao.TipoFonte.ORIGINAL),
        fonte_nome=dados.get("fonte_nome", ""),
        fonte_ano=dados.get("fonte_ano"),
        fonte_url=dados.get("fonte_url", ""),
        status=Questao.StatusQuestao.RASCUNHO,
        criado_por=usuario,
    )
    for alternativa in dados["alternativas"]:
        Alternativa.objects.create(
            questao=questao,
            chave=alternativa["chave"],
            texto=alternativa["texto"],
            correta=alternativa["correta"],
            ordem=alternativa["ordem"],
        )
    for conteudo in conteudos:
        QuestaoConteudo.objects.create(
            questao=questao,
            conteudo=conteudo,
            principal=conteudo == principal,
        )
    return questao


def criar_snapshot_manual(simulado, dados, conteudos, principal, usuario, salvar_no_banco=False, origem=QuestaoSimulado.OrigemQuestao.MANUAL):
    garantir_edicao_estrutural(simulado)
    validar_materia_simulado(simulado, conteudos)
    questao_origem = None
    with transaction.atomic():
        if salvar_no_banco:
            if not dados.get("codigo"):
                raise ValidationError("Informe um código para salvar no banco de questões.")
            materia = principal.materia
            questao_origem = criar_questao_banco_de_snapshot(
                dados,
                materia,
                conteudos,
                principal,
                usuario,
            )
        snapshot = QuestaoSimulado.objects.create(
            simulado=simulado,
            questao_origem=questao_origem,
            origem=origem,
            codigo_origem=dados.get("codigo", ""),
            enunciado=dados["enunciado"],
            explicacao=dados.get("explicacao", ""),
            dificuldade=dados.get("dificuldade", Questao.DificuldadeQuestao.MEDIA),
            tipo_fonte=dados.get("tipo_fonte", Questao.TipoFonte.ORIGINAL),
            fonte_nome=dados.get("fonte_nome", ""),
            fonte_ano=dados.get("fonte_ano"),
            fonte_url=dados.get("fonte_url", ""),
            ordem=proxima_ordem(simulado),
        )
        for alternativa in dados["alternativas"]:
            AlternativaSimulado.objects.create(
                questao_simulado=snapshot,
                chave=alternativa["chave"],
                texto=alternativa["texto"],
                correta=alternativa["correta"],
                ordem=alternativa["ordem"],
            )
        for conteudo in conteudos:
            QuestaoSimuladoConteudo.objects.create(
                questao_simulado=snapshot,
                conteudo=conteudo,
                principal=conteudo == principal,
            )
    return snapshot


def validar_json_importacao(texto, simulado=None, salvar_no_banco=False):
    try:
        payload = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ValidationError([f"JSON inválido: {exc.msg}."])
    if not isinstance(payload, dict) or not isinstance(payload.get("questoes"), list):
        raise ValidationError(['Campo "questoes" deve ser uma lista.'])
    if not payload["questoes"]:
        raise ValidationError(['Campo "questoes" não pode ser vazio.'])

    dificuldades = {choice.value for choice in Questao.DificuldadeQuestao}
    fontes = {choice.value for choice in Questao.TipoFonte}
    validadas = []
    erros = []
    codigos = set()

    for indice, item in enumerate(payload["questoes"], start=1):
        prefixo = f"Questão {indice}:"
        if not isinstance(item, dict):
            erros.append(f"{prefixo} item inválido.")
            continue
        codigo = " ".join((item.get("codigo") or "").split()).upper()
        enunciado = (item.get("enunciado") or "").strip()
        dificuldade = item.get("dificuldade") or Questao.DificuldadeQuestao.MEDIA
        tipo_fonte = item.get("tipo_fonte") or Questao.TipoFonte.ORIGINAL
        alternativas = item.get("alternativas")
        slugs = item.get("conteudos") or []
        principal_slug = item.get("conteudo_principal")

        if not enunciado:
            erros.append(f"{prefixo} enunciado é obrigatório.")
        if dificuldade not in dificuldades:
            erros.append(f'{prefixo} dificuldade "{dificuldade}" inválida.')
        if tipo_fonte not in fontes:
            erros.append(f'{prefixo} fonte "{tipo_fonte}" inválida.')
        if salvar_no_banco:
            if not codigo:
                erros.append(f"{prefixo} código é obrigatório para salvar no banco.")
            elif codigo in codigos or Questao.objects.filter(codigo=codigo).exists():
                erros.append(f'{prefixo} código "{codigo}" já existe.')
            codigos.add(codigo)
        if not isinstance(alternativas, list) or len(alternativas) < 2:
            erros.append(f"{prefixo} informe pelo menos 2 alternativas.")
            alternativas = []
        if not isinstance(slugs, list) or not slugs:
            erros.append(f"{prefixo} informe pelo menos 1 conteúdo.")
            slugs = []
        if principal_slug not in slugs:
            erros.append(f"{prefixo} conteúdo principal deve estar entre os conteúdos.")

        conteudos = []
        for slug in slugs:
            conteudo = Conteudo.objects.select_related("materia").filter(slug=slug).first()
            if not conteudo:
                erros.append(f'{prefixo} conteúdo "{slug}" não encontrado.')
            else:
                conteudos.append(conteudo)
        principal = next((conteudo for conteudo in conteudos if conteudo.slug == principal_slug), None)
        if simulado and conteudos:
            try:
                validar_materia_simulado(simulado, conteudos)
            except ValidationError:
                erros.append(f"{prefixo} matéria incoerente com o simulado.")

        alt_validadas = []
        chaves = set()
        corretas = 0
        for alt_indice, alternativa in enumerate(alternativas, start=1):
            chave = " ".join((alternativa.get("chave") or "").split()).upper()
            texto_alt = (alternativa.get("texto") or "").strip()
            correta = bool(alternativa.get("correta"))
            ordem = alternativa.get("ordem") or alt_indice
            if chave not in CHAVES_VALIDAS:
                erros.append(f'{prefixo} alternativa {alt_indice} possui chave inválida.')
            if chave in chaves:
                erros.append(f'{prefixo} alternativa {chave} duplicada.')
            if not texto_alt:
                erros.append(f"{prefixo} alternativa {chave or alt_indice} sem texto.")
            chaves.add(chave)
            corretas += 1 if correta else 0
            alt_validadas.append(
                {"chave": chave, "texto": texto_alt, "correta": correta, "ordem": ordem}
            )
        if corretas != 1:
            erros.append(f"{prefixo} informe exatamente 1 alternativa correta.")

        validadas.append(
            {
                "codigo": codigo,
                "enunciado": enunciado,
                "explicacao": item.get("explicacao", ""),
                "dificuldade": dificuldade,
                "tipo_fonte": tipo_fonte,
                "fonte_nome": item.get("fonte_nome", ""),
                "fonte_ano": item.get("fonte_ano"),
                "fonte_url": item.get("fonte_url", ""),
                "alternativas": alt_validadas,
                "conteudos": conteudos,
                "principal": principal,
            }
        )
    if erros:
        raise ValidationError(erros)
    return validadas


def importar_json(simulado, texto, usuario, salvar_no_banco=False):
    garantir_edicao_estrutural(simulado)
    questoes = validar_json_importacao(texto, simulado=simulado, salvar_no_banco=salvar_no_banco)
    criadas = []
    try:
        with transaction.atomic():
            for dados in questoes:
                criadas.append(
                    criar_snapshot_manual(
                        simulado,
                        dados,
                        dados["conteudos"],
                        dados["principal"],
                        usuario,
                        salvar_no_banco=salvar_no_banco,
                        origem=QuestaoSimulado.OrigemQuestao.JSON,
                    )
                )
    except IntegrityError as exc:
        raise ValidationError("Não foi possível importar o JSON. Verifique duplicidades.") from exc
    return criadas


def diagnostico_tentativa(tentativa):
    dados = defaultdict(lambda: {"questoes": 0, "acertos": 0, "conteudo": None})
    respostas = {
        resposta.questao_simulado_id: resposta
        for resposta in tentativa.respostas.select_related("questao_simulado")
    }
    relacoes = QuestaoSimuladoConteudo.objects.filter(
        questao_simulado__simulado=tentativa.simulado
    ).select_related("conteudo", "questao_simulado")
    for relacao in relacoes:
        chave = relacao.conteudo_id
        dados[chave]["conteudo"] = relacao
        dados[chave]["questoes"] += 1
        resposta = respostas.get(relacao.questao_simulado_id)
        if resposta and resposta.correta:
            dados[chave]["acertos"] += 1
    resultado = []
    for item in dados.values():
        total = item["questoes"]
        acertos = item["acertos"]
        resultado.append(
            {
                "relacao": item["conteudo"],
                "questoes": total,
                "acertos": acertos,
                "percentual": round((acertos / total) * 100, 2) if total else 0,
            }
        )
    return sorted(resultado, key=lambda item: (item["percentual"], -item["questoes"], item["relacao"].conteudo_titulo))
