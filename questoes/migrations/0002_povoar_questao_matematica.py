import json
from pathlib import Path

from django.db import migrations


def carregar_dados():
    caminho_json = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "questoes_matematica.json"
    )

    with open(caminho_json, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def criar_questoes_matematica(apps, schema_editor):
    Materia = apps.get_model("curriculo", "Materia")
    Conteudo = apps.get_model("curriculo", "Conteudo")
    Questao = apps.get_model("questoes", "Questao")
    Alternativa = apps.get_model("questoes", "Alternativa")
    QuestaoConteudo = apps.get_model("questoes", "QuestaoConteudo")

    dados = carregar_dados()
    materia = Materia.objects.get(slug=dados["materia"])

    for item in dados["questoes"]:
        questao, _ = Questao.objects.get_or_create(
            codigo=item["codigo"],
            defaults={
                "materia": materia,
                "enunciado": item["enunciado"],
                "explicacao": item.get("explicacao", ""),
                "dificuldade": item["dificuldade"],
                "tipo_fonte": item.get("tipo_fonte", "original"),
                "fonte_nome": item.get("fonte_nome", ""),
                "fonte_ano": item.get("fonte_ano"),
                "fonte_url": item.get("fonte_url", ""),
                "status": item["status"],
                "criado_por": None,
            },
        )

        for ordem, alternativa in enumerate(item["alternativas"], start=1):
            Alternativa.objects.get_or_create(
                questao=questao,
                chave=alternativa["chave"],
                defaults={
                    "texto": alternativa["texto"],
                    "correta": alternativa.get("correta", False),
                    "ordem": alternativa.get("ordem", ordem),
                },
            )

        for conteudo_slug in item["conteudos"]:
            conteudo = Conteudo.objects.get(
                materia=materia,
                slug=conteudo_slug,
            )
            QuestaoConteudo.objects.get_or_create(
                questao=questao,
                conteudo=conteudo,
                defaults={
                    "principal": conteudo_slug == item["conteudo_principal"]
                },
            )


def remover_questoes_matematica(apps, schema_editor):
    Questao = apps.get_model("questoes", "Questao")
    dados = carregar_dados()
    codigos = [item["codigo"] for item in dados["questoes"]]

    Questao.objects.filter(
        materia__slug=dados["materia"],
        codigo__in=codigos,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("curriculo", "0004_povoar_conteudo_matematica"),
        ("questoes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            criar_questoes_matematica,
            remover_questoes_matematica,
        ),
    ]
