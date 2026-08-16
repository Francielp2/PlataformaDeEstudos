import json
from pathlib import Path

from django.db import migrations


def criar_conteudos_matematica(apps, schema_editor):
    Materia = apps.get_model("curriculo", "Materia")
    Conteudo = apps.get_model("curriculo", "Conteudo")

    # Localiza o JSON dentro do app curriculo
    caminho_json = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "conteudos_matematica.json"
    )

    with open(caminho_json, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    # Busca a matéria criada pela migration inicial
    materia = Materia.objects.get(slug=dados["materia"])

    for item in dados["conteudos"]:
        Conteudo.objects.get_or_create(
            materia=materia,
            slug=item["slug"],
            defaults={
                "titulo": item["titulo"],
                "resumo": item["resumo"],
                "texto_estudo": item["texto_estudo"],
                "dificuldade": item["dificuldade"],
                "status": item["status"],
                "ordem_sugerida": item["ordem_sugerida"],
                "pai": None,
                "criado_por": None,
            },
        )


def remover_conteudos_matematica(apps, schema_editor):
    Conteudo = apps.get_model("curriculo", "Conteudo")

    caminho_json = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "conteudos_matematica.json"
    )

    with open(caminho_json, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    slugs = [item["slug"] for item in dados["conteudos"]]

    Conteudo.objects.filter(
        materia__slug=dados["materia"],
        slug__in=slugs,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        # COLOQUE AQUI A MIGRATION ANTERIOR REAL DO CURRICULO
        ("curriculo", "0003_conteudo"),
    ]

    operations = [
        migrations.RunPython(
            criar_conteudos_matematica,
            remover_conteudos_matematica,
        ),
    ]