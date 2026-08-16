from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, Prefetch, Q, Value, When
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from curriculo.models import Conteudo, Materia

from .forms import AlternativaFormSet, QuestaoForm, ResponderQuestaoForm
from .models import Alternativa, Questao, QuestaoConteudo, RespostaQuestao


STATUS_QUESTAO = {choice.value for choice in Questao.StatusQuestao} | {""}
DIFICULDADES_QUESTAO = {choice.value for choice in Questao.DificuldadeQuestao} | {""}
SESSAO_SEQUENCIA = "questoes_sequencia"


def staff_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('usuarios:login')}?next={request.path}")
        if not request.user.is_staff:
            messages.error(request, "Acesso negado. Esta área é restrita à administração.")
            return HttpResponseForbidden("Acesso negado. Esta área é restrita à administração.")
        return view_func(request, *args, **kwargs)

    return wrapper


def _ordem_dificuldade():
    return Case(
        When(dificuldade=Questao.DificuldadeQuestao.FACIL, then=Value(1)),
        When(dificuldade=Questao.DificuldadeQuestao.MEDIA, then=Value(2)),
        When(dificuldade=Questao.DificuldadeQuestao.DIFICIL, then=Value(3)),
        default=Value(9),
    )


def _questoes_publicadas():
    return (
        Questao.objects.filter(
            status=Questao.StatusQuestao.PUBLICADA,
            materia__ativa=True,
        )
        .select_related("materia")
        .prefetch_related("questao_conteudos__conteudo")
        .annotate(
            ordem_dificuldade=_ordem_dificuldade(),
            total_conteudos=Count("questao_conteudos", distinct=True),
        )
        .order_by("ordem_dificuldade", "total_conteudos", "codigo")
    )


def _aplicar_filtros_questoes(request, queryset):
    busca = request.GET.get("q", "").strip()
    materia_slug = request.GET.get("materia", "").strip()
    conteudo_id = request.GET.get("conteudo", "").strip()
    dificuldade = request.GET.get("dificuldade", "").strip()
    if dificuldade not in DIFICULDADES_QUESTAO:
        dificuldade = ""

    if busca:
        queryset = queryset.filter(Q(codigo__icontains=busca) | Q(enunciado__icontains=busca))
    if materia_slug:
        queryset = queryset.filter(materia__slug=materia_slug)
    if conteudo_id:
        queryset = queryset.filter(questao_conteudos__conteudo_id=conteudo_id)
    if dificuldade:
        queryset = queryset.filter(dificuldade=dificuldade)

    return queryset.distinct(), {
        "busca": busca,
        "materia_slug": materia_slug,
        "conteudo_id": conteudo_id,
        "dificuldade": dificuldade,
    }


def _registrar_resposta(usuario, questao, alternativa):
    if questao.status != Questao.StatusQuestao.PUBLICADA:
        raise ValidationError("Esta questão não está disponível para resolução.")
    if alternativa.questao_id != questao.id:
        raise ValidationError("A alternativa escolhida não pertence à questão.")
    resposta = RespostaQuestao(
        usuario=usuario,
        questao=questao,
        alternativa_escolhida=alternativa,
        correta=alternativa.correta,
    )
    resposta.full_clean()
    resposta.save()
    return resposta


@login_required(login_url="usuarios:login")
def exercicios_lista(request):
    questoes, filtros = _aplicar_filtros_questoes(request, _questoes_publicadas())
    materias = Materia.objects.filter(ativa=True)
    conteudos = Conteudo.objects.filter(
        materia__ativa=True,
        status=Conteudo.StatusConteudo.PUBLICADO,
    ).select_related("materia")
    query_params = request.GET.copy()
    query_params.pop("page", None)
    paginator = Paginator(questoes, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "questoes/exercicios_lista.html",
        {
            "page_obj": page_obj,
            "materias": materias,
            "conteudos": conteudos,
            "dificuldades": Questao.DificuldadeQuestao,
            "querystring": query_params.urlencode(),
            "total_encontrado": paginator.count,
            "active": "exercicios",
            **filtros,
        },
    )


@login_required(login_url="usuarios:login")
def questao_detalhe(request, pk):
    questao = get_object_or_404(
        _questoes_publicadas().prefetch_related("alternativas"),
        pk=pk,
    )
    form = ResponderQuestaoForm(request.POST or None, questao=questao)
    if request.method == "POST" and form.is_valid():
        resposta = _registrar_resposta(
            request.user,
            questao,
            form.cleaned_data["alternativa"],
        )
        return render(
            request,
            "questoes/questao_resultado.html",
            {"questao": questao, "resposta": resposta, "active": "exercicios"},
        )

    return render(
        request,
        "questoes/questao_detalhe.html",
        {"questao": questao, "form": form, "active": "exercicios"},
    )


@login_required(login_url="usuarios:login")
def iniciar_sequencia(request):
    questoes, filtros = _aplicar_filtros_questoes(request, _questoes_publicadas())
    ids = [str(pk) for pk in questoes.values_list("pk", flat=True)]
    request.session[SESSAO_SEQUENCIA] = {
        "ids": ids,
        "indice": 0,
        "acertos": 0,
        "erros": 0,
        "total": len(ids),
        "filtros": filtros,
    }
    return redirect("questoes:sequencia")


@login_required(login_url="usuarios:login")
def sequencia(request):
    dados = request.session.get(SESSAO_SEQUENCIA)
    if not dados:
        return redirect("questoes:exercicios_lista")

    ids = dados.get("ids", [])
    indice = dados.get("indice", 0)
    if indice >= len(ids):
        return redirect("questoes:sequencia_resumo")

    questao = get_object_or_404(
        _questoes_publicadas().prefetch_related("alternativas"),
        pk=ids[indice],
    )
    form = ResponderQuestaoForm(request.POST or None, questao=questao)
    if request.method == "POST" and form.is_valid():
        resposta = _registrar_resposta(
            request.user,
            questao,
            form.cleaned_data["alternativa"],
        )
        dados["indice"] = indice + 1
        if resposta.correta:
            dados["acertos"] += 1
        else:
            dados["erros"] += 1
        request.session[SESSAO_SEQUENCIA] = dados
        return render(
            request,
            "questoes/sequencia_resultado.html",
            {
                "questao": questao,
                "resposta": resposta,
                "proxima_posicao": dados["indice"] + 1,
                "total": dados["total"],
                "active": "exercicios",
            },
        )

    return render(
        request,
        "questoes/sequencia_questao.html",
        {
            "questao": questao,
            "form": form,
            "posicao": indice + 1,
            "total": dados["total"],
            "active": "exercicios",
        },
    )


@login_required(login_url="usuarios:login")
def sequencia_resumo(request):
    dados = request.session.get(SESSAO_SEQUENCIA)
    if not dados:
        return redirect("questoes:exercicios_lista")
    total = dados.get("acertos", 0) + dados.get("erros", 0)
    percentual = round((dados.get("acertos", 0) / total) * 100) if total else 0
    request.session.pop(SESSAO_SEQUENCIA, None)
    return render(
        request,
        "questoes/sequencia_resumo.html",
        {
            "respondidas": total,
            "acertos": dados.get("acertos", 0),
            "erros": dados.get("erros", 0),
            "percentual": percentual,
            "active": "exercicios",
        },
    )


@login_required(login_url="usuarios:login")
def historico(request):
    respostas = (
        RespostaQuestao.objects.filter(usuario=request.user)
        .select_related("questao", "questao__materia", "alternativa_escolhida")
        .prefetch_related("questao__questao_conteudos__conteudo")
    )
    paginator = Paginator(respostas, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "questoes/historico.html",
        {"page_obj": page_obj, "active": "exercicios"},
    )


@login_required(login_url="usuarios:login")
def resposta_detalhe(request, pk):
    resposta = get_object_or_404(
        RespostaQuestao.objects.select_related(
            "questao",
            "questao__materia",
            "alternativa_escolhida",
        ).prefetch_related("questao__alternativas", "questao__questao_conteudos__conteudo"),
        pk=pk,
        usuario=request.user,
    )
    return render(
        request,
        "questoes/resposta_detalhe.html",
        {"resposta": resposta, "active": "exercicios"},
    )


def _salvar_relacoes_conteudo(questao, conteudos, principal):
    QuestaoConteudo.objects.filter(questao=questao).delete()
    for conteudo in conteudos:
        relacao = QuestaoConteudo(
            questao=questao,
            conteudo=conteudo,
            principal=principal == conteudo,
        )
        relacao.full_clean()
        relacao.save()


@staff_required
def admin_questoes_lista(request):
    busca = request.GET.get("q", "").strip()
    materia_slug = request.GET.get("materia", "").strip()
    conteudo_id = request.GET.get("conteudo", "").strip()
    dificuldade = request.GET.get("dificuldade", "").strip()
    status = request.GET.get("status", "").strip()
    if dificuldade not in DIFICULDADES_QUESTAO:
        dificuldade = ""
    if status not in STATUS_QUESTAO:
        status = ""

    questoes = (
        Questao.objects.select_related("materia")
        .prefetch_related("questao_conteudos__conteudo")
        .order_by("codigo")
    )
    if busca:
        questoes = questoes.filter(Q(codigo__icontains=busca) | Q(enunciado__icontains=busca))
    if materia_slug:
        questoes = questoes.filter(materia__slug=materia_slug)
    if conteudo_id:
        questoes = questoes.filter(questao_conteudos__conteudo_id=conteudo_id)
    if dificuldade:
        questoes = questoes.filter(dificuldade=dificuldade)
    if status:
        questoes = questoes.filter(status=status)

    paginator = Paginator(questoes.distinct(), 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(
        request,
        "questoes/admin_questoes_lista.html",
        {
            "page_obj": page_obj,
            "materias": Materia.objects.order_by("ordem_exibicao", "nome"),
            "conteudos": Conteudo.objects.select_related("materia").order_by("materia__nome", "titulo"),
            "dificuldades": Questao.DificuldadeQuestao,
            "status_choices": Questao.StatusQuestao,
            "busca": busca,
            "materia_slug": materia_slug,
            "conteudo_id": conteudo_id,
            "dificuldade": dificuldade,
            "status": status,
            "querystring": query_params.urlencode(),
            "total_encontrado": paginator.count,
            "active": "admin_questoes",
        },
    )


@staff_required
def admin_questao_criar(request):
    questao = Questao(criado_por=request.user)
    form = QuestaoForm(request.POST or None, instance=questao)
    formset = AlternativaFormSet(request.POST or None, instance=questao, prefix="alternativas")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            with transaction.atomic():
                questao = form.save(commit=False)
                questao.criado_por = request.user
                questao.full_clean()
                questao.save()
                formset.instance = questao
                formset.save()
                _salvar_relacoes_conteudo(
                    questao,
                    form.cleaned_data["conteudos"],
                    form.cleaned_data["conteudo_principal"],
                )
                if questao.status == Questao.StatusQuestao.PUBLICADA:
                    questao.validar_publicacao()
            messages.success(request, "Questão cadastrada com sucesso.")
            return redirect("questoes_admin:admin_questao_detalhe", pk=questao.pk)
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, exc)

    return render(
        request,
        "questoes/admin_questao_form.html",
        {
            "form": form,
            "formset": formset,
            "titulo": "Criar questão",
            "active": "admin_questoes",
        },
    )


@staff_required
def admin_questao_detalhe(request, pk):
    questao = get_object_or_404(
        Questao.objects.select_related("materia", "criado_por").prefetch_related(
            "alternativas",
            "questao_conteudos__conteudo",
        ),
        pk=pk,
    )
    return render(
        request,
        "questoes/admin_questao_detalhe.html",
        {"questao": questao, "active": "admin_questoes"},
    )


@staff_required
def admin_questao_editar(request, pk):
    questao = get_object_or_404(Questao, pk=pk)
    criado_por_original = questao.criado_por
    form = QuestaoForm(request.POST or None, instance=questao)
    formset = AlternativaFormSet(request.POST or None, instance=questao, prefix="alternativas")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            with transaction.atomic():
                questao = form.save(commit=False)
                questao.criado_por = criado_por_original
                questao.full_clean()
                questao.save()
                formset.save()
                _salvar_relacoes_conteudo(
                    questao,
                    form.cleaned_data["conteudos"],
                    form.cleaned_data["conteudo_principal"],
                )
                if questao.status == Questao.StatusQuestao.PUBLICADA:
                    questao.validar_publicacao()
            messages.success(request, "Questão atualizada com sucesso.")
            return redirect("questoes_admin:admin_questao_detalhe", pk=questao.pk)
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, exc)

    return render(
        request,
        "questoes/admin_questao_form.html",
        {
            "form": form,
            "formset": formset,
            "titulo": "Editar questão",
            "active": "admin_questoes",
        },
    )


@require_POST
@staff_required
def admin_questao_alterar_status(request, pk, status):
    if status not in {choice.value for choice in Questao.StatusQuestao}:
        messages.error(request, "Status de questão inválido.")
        return redirect("questoes_admin:admin_questoes_lista")
    questao = get_object_or_404(Questao, pk=pk)
    try:
        if status == Questao.StatusQuestao.PUBLICADA:
            questao.publicar()
            messages.success(request, "Questão publicada com sucesso.")
        else:
            questao.status = status
            questao.save(update_fields=["status", "atualizado_em"])
            if status == Questao.StatusQuestao.ARQUIVADA:
                messages.success(request, "Questão arquivada com sucesso.")
            else:
                messages.success(request, "Questão retornada para rascunho.")
    except ValidationError as exc:
        messages.error(request, exc)
    return redirect("questoes_admin:admin_questoes_lista")


@staff_required
def admin_respostas_lista(request):
    respostas = RespostaQuestao.objects.select_related(
        "usuario",
        "questao",
        "questao__materia",
        "alternativa_escolhida",
    )
    busca = request.GET.get("q", "").strip()
    resultado = request.GET.get("resultado", "").strip()
    if busca:
        respostas = respostas.filter(
            Q(usuario__email__icontains=busca)
            | Q(questao__codigo__icontains=busca)
            | Q(questao__enunciado__icontains=busca)
        )
    if resultado == "acertos":
        respostas = respostas.filter(correta=True)
    elif resultado == "erros":
        respostas = respostas.filter(correta=False)
    paginator = Paginator(respostas, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "questoes/admin_respostas_lista.html",
        {
            "page_obj": page_obj,
            "busca": busca,
            "resultado": resultado,
            "active": "admin_questoes",
        },
    )


@staff_required
def admin_resposta_detalhe(request, pk):
    resposta = get_object_or_404(
        RespostaQuestao.objects.select_related(
            "usuario",
            "questao",
            "questao__materia",
            "alternativa_escolhida",
        ).prefetch_related("questao__alternativas", "questao__questao_conteudos__conteudo"),
        pk=pk,
    )
    return render(
        request,
        "questoes/admin_resposta_detalhe.html",
        {"resposta": resposta, "active": "admin_questoes"},
    )
