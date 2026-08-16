from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from curriculo.models import Conteudo, Materia
from questoes.models import Questao

from .models import ConteudoEstudado, ItemMinhaLista


TIPOS_MINHA_LISTA = {"", "materias", "conteudos", "questoes"}
DIFICULDADES_CONTEUDO = {choice.value for choice in Conteudo.DificuldadeConteudo} | {""}


def _redirect_seguro(request, fallback):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(fallback)


def _ids_minha_lista(usuario):
    itens = ItemMinhaLista.objects.filter(usuario=usuario)
    return {
        "ids_materias_minha_lista": set(
            itens.filter(materia__isnull=False).values_list("materia_id", flat=True)
        ),
        "ids_conteudos_minha_lista": set(
            itens.filter(conteudo__isnull=False).values_list("conteudo_id", flat=True)
        ),
        "ids_questoes_minha_lista": set(
            itens.filter(questao__isnull=False).values_list("questao_id", flat=True)
        ),
    }


def ids_organizacao_usuario(usuario):
    contexto = _ids_minha_lista(usuario)
    contexto["ids_conteudos_estudados"] = set(
        ConteudoEstudado.objects.filter(usuario=usuario).values_list(
            "conteudo_id",
            flat=True,
        )
    )
    return contexto


def _alternar_item(request, **alvo):
    item = ItemMinhaLista.objects.filter(usuario=request.user, **alvo).first()
    objeto = next(valor for valor in alvo.values() if valor is not None)
    tipo = "Item"
    if "materia" in alvo:
        tipo = "Matéria"
    elif "conteudo" in alvo:
        tipo = "Conteúdo"
    elif "questao" in alvo:
        tipo = "Questão"

    if item:
        item.delete()
        messages.success(request, f"{tipo} removida da Minha Lista.")
    else:
        try:
            item = ItemMinhaLista(usuario=request.user, **alvo)
            item.full_clean()
            item.save()
            messages.success(request, f"{objeto} adicionada à Minha Lista.")
        except (ValidationError, IntegrityError):
            messages.error(request, "Não foi possível atualizar a Minha Lista.")
    return _redirect_seguro(request, "estudos:minha_lista")


@require_POST
@login_required(login_url="usuarios:login")
def remover_item_minha_lista(request, pk):
    item = get_object_or_404(ItemMinhaLista, pk=pk, usuario=request.user)
    item.delete()
    messages.success(request, "Item removido da Minha Lista.")
    return _redirect_seguro(request, "estudos:minha_lista")


@login_required(login_url="usuarios:login")
def minha_lista(request):
    tipo = request.GET.get("tipo", "").strip()
    if tipo not in TIPOS_MINHA_LISTA:
        tipo = ""

    itens = (
        ItemMinhaLista.objects.filter(usuario=request.user)
        .select_related(
            "materia",
            "conteudo",
            "conteudo__materia",
            "questao",
            "questao__materia",
        )
        .prefetch_related("questao__questao_conteudos__conteudo")
    )
    if tipo == "materias":
        itens = itens.filter(materia__isnull=False)
    elif tipo == "conteudos":
        itens = itens.filter(conteudo__isnull=False)
    elif tipo == "questoes":
        itens = itens.filter(questao__isnull=False)

    return render(
        request,
        "estudos/minha_lista.html",
        {
            "itens": itens,
            "tipo": tipo,
            "active": "minha-lista",
            **ids_organizacao_usuario(request.user),
        },
    )


@login_required(login_url="usuarios:login")
def conteudos_estudados(request):
    materia_slug = request.GET.get("materia", "").strip()
    dificuldade = request.GET.get("dificuldade", "").strip()
    busca = request.GET.get("q", "").strip()
    if dificuldade not in DIFICULDADES_CONTEUDO:
        dificuldade = ""

    estudados = ConteudoEstudado.objects.filter(usuario=request.user).select_related(
        "conteudo",
        "conteudo__materia",
    )
    if materia_slug:
        estudados = estudados.filter(conteudo__materia__slug=materia_slug)
    if dificuldade:
        estudados = estudados.filter(conteudo__dificuldade=dificuldade)
    if busca:
        estudados = estudados.filter(conteudo__titulo__icontains=busca)

    return render(
        request,
        "estudos/conteudos_estudados.html",
        {
            "estudados": estudados,
            "materias": Materia.objects.filter(ativa=True),
            "dificuldades": Conteudo.DificuldadeConteudo,
            "materia_slug": materia_slug,
            "dificuldade": dificuldade,
            "busca": busca,
            "active": "estudados",
            **ids_organizacao_usuario(request.user),
        },
    )


@require_POST
@login_required(login_url="usuarios:login")
def alternar_materia_minha_lista(request, pk):
    materia = get_object_or_404(Materia, pk=pk, ativa=True)
    return _alternar_item(request, materia=materia)


@require_POST
@login_required(login_url="usuarios:login")
def alternar_conteudo_minha_lista(request, pk):
    conteudo = get_object_or_404(
        Conteudo,
        pk=pk,
        materia__ativa=True,
        status=Conteudo.StatusConteudo.PUBLICADO,
    )
    return _alternar_item(request, conteudo=conteudo)


@require_POST
@login_required(login_url="usuarios:login")
def alternar_questao_minha_lista(request, pk):
    questao = get_object_or_404(
        Questao,
        pk=pk,
        materia__ativa=True,
        status=Questao.StatusQuestao.PUBLICADA,
    )
    return _alternar_item(request, questao=questao)


@require_POST
@login_required(login_url="usuarios:login")
def alternar_conteudo_estudado(request, pk):
    estudado = ConteudoEstudado.objects.filter(
        usuario=request.user,
        conteudo_id=pk,
    ).first()
    if estudado:
        estudado.delete()
        messages.success(request, "Conteúdo removido dos estudados.")
    else:
        conteudo = get_object_or_404(
            Conteudo,
            pk=pk,
            materia__ativa=True,
            status=Conteudo.StatusConteudo.PUBLICADO,
        )
        ConteudoEstudado.objects.create(usuario=request.user, conteudo=conteudo)
        messages.success(request, "Conteúdo marcado como estudado.")
    return _redirect_seguro(request, "estudos:conteudos_estudados")
