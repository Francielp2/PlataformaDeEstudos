from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from curriculo.models import Conteudo, Materia
from estudos.views import ids_organizacao_usuario
from questoes.models import Questao

from .forms import (
    AlternativaSimuladoFormSet,
    ImportarJsonForm,
    QuestaoSimuladoForm,
    ResponderSimuladoForm,
    SelecionarQuestoesForm,
    SimuladoForm,
)
from .models import AlternativaSimulado, QuestaoSimulado, RespostaSimulado, Simulado, TentativaSimulado
from .services import (
    criar_snapshot_de_questao,
    criar_snapshot_manual,
    diagnostico_tentativa,
    garantir_edicao_estrutural,
    importar_json,
)


STATUS_SIMULADO = {choice.value for choice in Simulado.StatusSimulado} | {""}
TIPOS_SIMULADO = {choice.value for choice in Simulado.TipoSimulado} | {""}
DIFICULDADES_QUESTAO = {choice.value for choice in Questao.DificuldadeQuestao} | {""}


def staff_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('usuarios:login')}?next={request.path}")
        if not request.user.is_staff:
            messages.error(request, "Acesso negado. Esta área é restrita à administração.")
            return HttpResponseForbidden("Acesso negado. Esta área é restrita à administração.")
        return view_func(request, *args, **kwargs)

    return wrapper


def _simulados_publicados():
    return Simulado.objects.filter(status=Simulado.StatusSimulado.PUBLICADO).select_related("materia")


def _filtrar_simulados(request, queryset):
    busca = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    materia_slug = request.GET.get("materia", "").strip()
    status = request.GET.get("status", "").strip()
    if tipo not in TIPOS_SIMULADO:
        tipo = ""
    if status not in STATUS_SIMULADO:
        status = ""
    if busca:
        queryset = queryset.filter(Q(titulo__icontains=busca) | Q(descricao__icontains=busca))
    if tipo:
        queryset = queryset.filter(tipo=tipo)
    if materia_slug:
        queryset = queryset.filter(materia__slug=materia_slug)
    if status:
        queryset = queryset.filter(status=status)
    return queryset, {"busca": busca, "tipo": tipo, "materia_slug": materia_slug, "status": status}


def _questoes_banco_filtradas(request, simulado):
    busca = request.GET.get("q", "").strip()
    materia_slug = request.GET.get("materia", "").strip()
    conteudo_id = request.GET.get("conteudo", "").strip()
    dificuldade = request.GET.get("dificuldade", "").strip()
    if dificuldade not in DIFICULDADES_QUESTAO:
        dificuldade = ""
    questoes = Questao.objects.filter(status=Questao.StatusQuestao.PUBLICADA).select_related("materia").prefetch_related("questao_conteudos__conteudo")
    if simulado.tipo == Simulado.TipoSimulado.POR_MATERIA:
        questoes = questoes.filter(materia=simulado.materia)
    if busca:
        questoes = questoes.filter(Q(codigo__icontains=busca) | Q(enunciado__icontains=busca))
    if materia_slug:
        questoes = questoes.filter(materia__slug=materia_slug)
    if conteudo_id:
        questoes = questoes.filter(questao_conteudos__conteudo_id=conteudo_id)
    if dificuldade:
        questoes = questoes.filter(dificuldade=dificuldade)
    return questoes.distinct().order_by("codigo"), {
        "busca": busca,
        "materia_slug": materia_slug,
        "conteudo_id": conteudo_id,
        "dificuldade": dificuldade,
    }


def _salvar_alternativas_formset(formset):
    ordens_usadas = set()
    proxima = 1
    for form in formset.forms:
        if not form.cleaned_data:
            continue
        alternativa = form.instance
        if form.cleaned_data.get("ordem") is None:
            while proxima in ordens_usadas:
                proxima += 1
            alternativa.ordem = proxima
        else:
            alternativa.ordem = form.cleaned_data["ordem"]
        ordens_usadas.add(alternativa.ordem)
    formset.save()


def _expirar_se_necessario(tentativa):
    limite = tentativa.simulado.tempo_limite
    if not limite or tentativa.finalizada:
        return False
    if timezone.now() >= tentativa.iniciada_em + timedelta(minutes=limite):
        tentativa.finalizar()
        return True
    return False


def _tempo_restante_segundos(tentativa):
    limite = tentativa.simulado.tempo_limite
    if not limite:
        return None
    fim = tentativa.iniciada_em + timedelta(minutes=limite)
    return max(0, int((fim - timezone.now()).total_seconds()))


def _registrar_resposta(tentativa, questao, alternativa):
    if tentativa.finalizada:
        raise ValidationError("Tentativa finalizada não pode ser alterada.")
    if questao.simulado_id != tentativa.simulado_id:
        raise ValidationError("A questão não pertence a esta tentativa.")
    if alternativa and alternativa.questao_simulado_id != questao.id:
        raise ValidationError("A alternativa não pertence à questão.")
    if not alternativa:
        RespostaSimulado.objects.filter(tentativa=tentativa, questao_simulado=questao).delete()
        return None
    resposta, _ = RespostaSimulado.objects.update_or_create(
        tentativa=tentativa,
        questao_simulado=questao,
        defaults={"alternativa_escolhida": alternativa},
    )
    resposta.full_clean()
    resposta.save()
    return resposta


@login_required(login_url="usuarios:login")
def simulados_lista(request):
    simulados, filtros = _filtrar_simulados(request, _simulados_publicados())
    simulados = simulados.annotate(total_questoes=Count("questoes", distinct=True))
    materias = Materia.objects.filter(ativa=True)
    tentativas = TentativaSimulado.objects.filter(usuario=request.user).values("simulado_id", "status")
    ids_realizados = {item["simulado_id"] for item in tentativas if item["status"] == TentativaSimulado.StatusTentativa.FINALIZADA}
    ids_em_andamento = {item["simulado_id"] for item in tentativas if item["status"] == TentativaSimulado.StatusTentativa.EM_ANDAMENTO}
    paginator = Paginator(simulados, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "simulados/simulados_lista.html",
        {
            "page_obj": page_obj,
            "materias": materias,
            "tipo_choices": Simulado.TipoSimulado,
            "ids_realizados": ids_realizados,
            "ids_em_andamento": ids_em_andamento,
            "active": "fazer-simulado",
            **ids_organizacao_usuario(request.user),
            **filtros,
        },
    )


@login_required(login_url="usuarios:login")
def meus_simulados(request):
    tentativas = TentativaSimulado.objects.filter(usuario=request.user).select_related("simulado", "simulado__materia")
    paginator = Paginator(tentativas, 15)
    return render(
        request,
        "simulados/meus_simulados.html",
        {"page_obj": paginator.get_page(request.GET.get("page")), "active": "meus-simulados"},
    )


@require_POST
@login_required(login_url="usuarios:login")
def iniciar_simulado(request, slug):
    simulado = get_object_or_404(_simulados_publicados(), slug=slug)
    tentativa = TentativaSimulado.objects.filter(
        usuario=request.user,
        simulado=simulado,
        status=TentativaSimulado.StatusTentativa.EM_ANDAMENTO,
    ).first()
    if not tentativa:
        tentativa = TentativaSimulado.objects.create(
            usuario=request.user,
            simulado=simulado,
            total_questoes=simulado.questoes.count(),
        )
    return redirect("simulados:tentativa_questao", pk=tentativa.pk, ordem=1)


@login_required(login_url="usuarios:login")
def tentativa_questao(request, pk, ordem):
    tentativa = get_object_or_404(
        TentativaSimulado.objects.select_related("simulado"),
        pk=pk,
        usuario=request.user,
    )
    if _expirar_se_necessario(tentativa):
        messages.warning(request, "O tempo limite foi encerrado e a tentativa foi finalizada.")
        return redirect("simulados:resultado_tentativa", pk=tentativa.pk)
    if tentativa.finalizada:
        return redirect("simulados:resultado_tentativa", pk=tentativa.pk)
    questoes = list(tentativa.simulado.questoes.prefetch_related("alternativas"))
    total = len(questoes)
    if not total:
        messages.error(request, "Este simulado não possui questões.")
        return redirect("simulados:simulados_lista")
    ordem = min(max(ordem, 1), total)
    questao = questoes[ordem - 1]
    resposta_atual = RespostaSimulado.objects.filter(tentativa=tentativa, questao_simulado=questao).first()
    form = ResponderSimuladoForm(request.POST or None, questao=questao, resposta=resposta_atual)
    if request.method == "POST" and form.is_valid():
        try:
            _registrar_resposta(tentativa, questao, form.cleaned_data.get("alternativa"))
            acao = request.POST.get("acao", "proxima")
            if acao == "finalizar":
                return redirect("simulados:finalizar_tentativa", pk=tentativa.pk)
            proxima = ordem - 1 if acao == "anterior" else ordem + 1
            return redirect("simulados:tentativa_questao", pk=tentativa.pk, ordem=min(max(proxima, 1), total))
        except ValidationError as exc:
            form.add_error(None, exc)
    respondidas = set(tentativa.respostas.values_list("questao_simulado_id", flat=True))
    return render(
        request,
        "simulados/tentativa_questao.html",
        {
            "tentativa": tentativa,
            "questao": questao,
            "form": form,
            "ordem": ordem,
            "total": total,
            "respondidas": respondidas,
            "questoes": questoes,
            "tempo_restante_segundos": _tempo_restante_segundos(tentativa),
            "active": "fazer-simulado",
        },
    )


@login_required(login_url="usuarios:login")
def finalizar_tentativa(request, pk):
    tentativa = get_object_or_404(
        TentativaSimulado.objects.select_related("simulado"),
        pk=pk,
        usuario=request.user,
    )
    if tentativa.finalizada:
        return redirect("simulados:resultado_tentativa", pk=tentativa.pk)
    total = tentativa.simulado.questoes.count()
    respondidas = tentativa.respostas.count()
    pendentes = total - respondidas
    if request.method == "POST":
        tentativa.finalizar()
        messages.success(request, "Simulado finalizado.")
        return redirect("simulados:resultado_tentativa", pk=tentativa.pk)
    return render(
        request,
        "simulados/finalizar_tentativa.html",
        {"tentativa": tentativa, "pendentes": pendentes, "active": "fazer-simulado"},
    )


@login_required(login_url="usuarios:login")
def resultado_tentativa(request, pk):
    tentativa = get_object_or_404(
        TentativaSimulado.objects.select_related("simulado", "simulado__materia"),
        pk=pk,
        usuario=request.user,
    )
    if not tentativa.finalizada:
        return redirect("simulados:tentativa_questao", pk=tentativa.pk, ordem=1)
    diagnostico = diagnostico_tentativa(tentativa)
    atencao = diagnostico[:3]
    return render(
        request,
        "simulados/resultado_tentativa.html",
        {"tentativa": tentativa, "diagnostico": diagnostico, "atencao": atencao, "active": "meus-simulados"},
    )


@login_required(login_url="usuarios:login")
def revisao_tentativa(request, pk):
    tentativa = get_object_or_404(
        TentativaSimulado.objects.select_related("simulado"),
        pk=pk,
        usuario=request.user,
        status=TentativaSimulado.StatusTentativa.FINALIZADA,
    )
    respostas = {
        resposta.questao_simulado_id: resposta
        for resposta in tentativa.respostas.select_related("alternativa_escolhida")
    }
    questoes = []
    for questao in tentativa.simulado.questoes.prefetch_related("alternativas"):
        resposta = respostas.get(questao.id)
        questoes.append(
            {
                "ordem": questao.ordem,
                "enunciado": questao.enunciado,
                "alternativas": [
                    {"id": alternativa.id, "chave": alternativa.chave, "texto": alternativa.texto}
                    for alternativa in questao.alternativas.order_by("ordem")
                ],
                "resposta_id": resposta.alternativa_escolhida_id if resposta else None,
                "resposta_chave": resposta.alternativa_chave if resposta else "",
                "correta": resposta.correta if resposta else False,
                "respondida": bool(resposta),
            }
        )
    return render(
        request,
        "simulados/revisao_tentativa.html",
        {"tentativa": tentativa, "questoes": questoes, "active": "meus-simulados"},
    )


@staff_required
def admin_simulados_lista(request):
    simulados, filtros = _filtrar_simulados(
        request,
        Simulado.objects.select_related("materia", "criado_por").annotate(
            total_questoes=Count("questoes", distinct=True),
            total_tentativas=Count("tentativas", distinct=True),
        ),
    )
    simulados = simulados.order_by("ordem_exibicao", "titulo")
    paginator = Paginator(simulados, 10)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(
        request,
        "simulados/admin_simulados_lista.html",
        {
            "page_obj": paginator.get_page(request.GET.get("page")),
            "materias": Materia.objects.order_by("ordem_exibicao", "nome"),
            "tipo_choices": Simulado.TipoSimulado,
            "status_choices": Simulado.StatusSimulado,
            "querystring": query_params.urlencode(),
            "total_encontrado": paginator.count,
            "total_rascunhos": Simulado.objects.filter(
                status=Simulado.StatusSimulado.RASCUNHO
            ).count(),
            "active": "admin_simulados",
            **filtros,
        },
    )


@require_POST
@staff_required
def admin_simulados_publicar_rascunhos(request):
    simulados = Simulado.objects.filter(
        status=Simulado.StatusSimulado.RASCUNHO
    ).prefetch_related("questoes__alternativas", "questoes__conteudos__conteudo")
    publicados = 0
    invalidos = 0

    for simulado in simulados:
        try:
            simulado.publicar()
            publicados += 1
        except ValidationError:
            invalidos += 1

    if publicados:
        messages.success(request, f"{publicados} simulado(s) publicado(s) com sucesso.")
    if invalidos:
        messages.warning(
            request,
            f"{invalidos} simulado(s) permaneceram em rascunho por estarem incompletos.",
        )
    if not publicados and not invalidos:
        messages.info(request, "Não há simulados em rascunho para publicar.")
    return redirect("simulados_admin:admin_simulados_lista")


@staff_required
def admin_simulado_criar(request):
    form = SimuladoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        simulado = form.save(commit=False)
        simulado.criado_por = request.user
        try:
            if simulado.status == Simulado.StatusSimulado.PUBLICADO:
                simulado.publicado_em = timezone.now()
            simulado.full_clean()
            simulado.save()
            if simulado.status == Simulado.StatusSimulado.PUBLICADO:
                simulado.publicar()
            messages.success(request, "Simulado cadastrado com sucesso.")
            return redirect("simulados_admin:admin_simulado_detalhe", pk=simulado.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "simulados/admin_simulado_form.html", {"form": form, "titulo": "Criar simulado", "active": "admin_simulados"})


@staff_required
def admin_simulado_editar(request, pk):
    simulado = get_object_or_404(Simulado, pk=pk)
    status_original = simulado.status
    form = SimuladoForm(request.POST or None, instance=simulado)
    if request.method == "POST" and form.is_valid():
        simulado = form.save(commit=False)
        try:
            simulado.full_clean()
            if simulado.status == Simulado.StatusSimulado.PUBLICADO and status_original != Simulado.StatusSimulado.PUBLICADO:
                simulado.publicar()
            else:
                simulado.save()
            messages.success(request, "Simulado atualizado com sucesso.")
            return redirect("simulados_admin:admin_simulado_detalhe", pk=simulado.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "simulados/admin_simulado_form.html", {"form": form, "titulo": "Editar simulado", "active": "admin_simulados"})


@staff_required
def admin_simulado_detalhe(request, pk):
    simulado = get_object_or_404(
        Simulado.objects.select_related("materia", "criado_por").prefetch_related(
            "questoes__alternativas",
            "questoes__conteudos__conteudo",
        ),
        pk=pk,
    )
    return render(
        request,
        "simulados/admin_simulado_detalhe.html",
        {
            "simulado": simulado,
            "total_tentativas": simulado.tentativas.count(),
            "pode_editar_estrutura": not simulado.tentativas.exists(),
            "active": "admin_simulados",
        },
    )


@require_POST
@staff_required
def admin_simulado_publicar(request, pk):
    simulado = get_object_or_404(Simulado, pk=pk)
    try:
        simulado.publicar()
        messages.success(request, "Simulado publicado com sucesso.")
    except ValidationError as exc:
        messages.error(request, exc)
    return redirect("simulados_admin:admin_simulado_detalhe", pk=simulado.pk)


@require_POST
@staff_required
def admin_simulado_arquivar(request, pk):
    simulado = get_object_or_404(Simulado, pk=pk)
    simulado.status = Simulado.StatusSimulado.ARQUIVADO
    simulado.save(update_fields=["status", "atualizado_em"])
    messages.success(request, "Simulado arquivado com sucesso.")
    return redirect("simulados_admin:admin_simulados_lista")


@require_POST
@staff_required
def admin_simulado_duplicar(request, pk):
    original = get_object_or_404(Simulado.objects.prefetch_related("questoes__alternativas", "questoes__conteudos__conteudo"), pk=pk)
    with transaction.atomic():
        novo = Simulado.objects.create(
            titulo=f"{original.titulo} (cópia)",
            descricao=original.descricao,
            tipo=original.tipo,
            materia=original.materia,
            status=Simulado.StatusSimulado.RASCUNHO,
            tempo_limite=original.tempo_limite,
            ordem_exibicao=original.ordem_exibicao,
            criado_por=request.user,
        )
        for questao in original.questoes.all():
            copia = QuestaoSimulado.objects.create(
                simulado=novo,
                questao_origem=questao.questao_origem,
                origem=questao.origem,
                codigo_origem=questao.codigo_origem,
                enunciado=questao.enunciado,
                explicacao=questao.explicacao,
                dificuldade=questao.dificuldade,
                tipo_fonte=questao.tipo_fonte,
                fonte_nome=questao.fonte_nome,
                fonte_ano=questao.fonte_ano,
                fonte_url=questao.fonte_url,
                ordem=questao.ordem,
            )
            for alternativa in questao.alternativas.all():
                AlternativaSimulado.objects.create(
                    questao_simulado=copia,
                    chave=alternativa.chave,
                    texto=alternativa.texto,
                    correta=alternativa.correta,
                    ordem=alternativa.ordem,
                )
            for relacao in questao.conteudos.all():
                relacao.pk = None
                relacao.questao_simulado = copia
                relacao.save()
    messages.success(request, "Simulado duplicado como rascunho.")
    return redirect("simulados_admin:admin_simulado_detalhe", pk=novo.pk)


@staff_required
def admin_simulado_questoes(request, pk):
    simulado = get_object_or_404(Simulado.objects.prefetch_related("questoes__alternativas", "questoes__conteudos__conteudo"), pk=pk)
    return render(request, "simulados/admin_simulado_questoes.html", {"simulado": simulado, "pode_editar_estrutura": not simulado.tentativas.exists(), "active": "admin_simulados"})


@staff_required
def admin_adicionar_questoes_banco(request, pk):
    simulado = get_object_or_404(Simulado, pk=pk)
    questoes, filtros = _questoes_banco_filtradas(request, simulado)
    form = SelecionarQuestoesForm(request.POST or None, queryset=questoes)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                for questao in form.cleaned_data["questoes"]:
                    criar_snapshot_de_questao(simulado, questao)
            messages.success(request, "Questões adicionadas ao simulado.")
            return redirect("simulados_admin:admin_simulado_questoes", pk=simulado.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "simulados/admin_adicionar_banco.html",
        {
            "simulado": simulado,
            "form": form,
            "questoes": questoes[:100],
            "materias": Materia.objects.order_by("ordem_exibicao", "nome"),
            "conteudos": Conteudo.objects.select_related("materia").order_by("materia__nome", "titulo"),
            "dificuldades": Questao.DificuldadeQuestao,
            "active": "admin_simulados",
            **filtros,
        },
    )


@staff_required
def admin_nova_questao_simulado(request, pk):
    simulado = get_object_or_404(Simulado, pk=pk)
    questao = QuestaoSimulado(simulado=simulado)
    form = QuestaoSimuladoForm(request.POST or None, instance=questao, simulado=simulado)
    formset = AlternativaSimuladoFormSet(request.POST or None, instance=questao, prefix="alternativas")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            alternativas = []
            for indice, alt_form in enumerate(formset.forms, start=1):
                if not alt_form.cleaned_data:
                    continue
                alternativas.append(
                    {
                        "chave": alt_form.cleaned_data["chave"],
                        "texto": alt_form.cleaned_data["texto"],
                        "correta": alt_form.cleaned_data["correta"],
                        "ordem": alt_form.cleaned_data.get("ordem") or indice,
                    }
                )
            if len(alternativas) < 2 or sum(1 for alt in alternativas if alt["correta"]) != 1:
                raise ValidationError("A questão deve ter pelo menos 2 alternativas e exatamente 1 correta.")
            dados = form.cleaned_data.copy()
            dados["alternativas"] = alternativas
            criar_snapshot_manual(
                simulado,
                dados,
                list(form.cleaned_data["conteudos"]),
                form.cleaned_data["conteudo_principal"],
                request.user,
                salvar_no_banco=form.cleaned_data["salvar_no_banco"],
            )
            messages.success(request, "Questão adicionada ao simulado.")
            return redirect("simulados_admin:admin_simulado_questoes", pk=simulado.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "simulados/admin_questao_form.html", {"form": form, "formset": formset, "simulado": simulado, "active": "admin_simulados"})


@staff_required
def admin_importar_json(request, pk):
    simulado = get_object_or_404(Simulado, pk=pk)
    form = ImportarJsonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            criadas = importar_json(
                simulado,
                form.cleaned_data["json_questoes"],
                request.user,
                salvar_no_banco=form.cleaned_data["salvar_no_banco"],
            )
            messages.success(request, f"{len(criadas)} questão(ões) importada(s).")
            return redirect("simulados_admin:admin_simulado_questoes", pk=simulado.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "simulados/admin_importar_json.html", {"form": form, "simulado": simulado, "active": "admin_simulados"})


@require_POST
@staff_required
def admin_remover_questao_simulado(request, pk, questao_pk):
    simulado = get_object_or_404(Simulado, pk=pk)
    try:
        garantir_edicao_estrutural(simulado)
        QuestaoSimulado.objects.filter(simulado=simulado, pk=questao_pk).delete()
        for indice, questao in enumerate(simulado.questoes.order_by("ordem", "criado_em"), start=1):
            if questao.ordem != indice:
                questao.ordem = indice
                questao.save(update_fields=["ordem"])
        messages.success(request, "Questão removida do simulado.")
    except ValidationError as exc:
        messages.error(request, exc)
    return redirect("simulados_admin:admin_simulado_questoes", pk=simulado.pk)


@require_POST
@staff_required
def admin_mover_questao_simulado(request, pk, questao_pk, direcao):
    simulado = get_object_or_404(Simulado, pk=pk)
    try:
        garantir_edicao_estrutural(simulado)
        questoes = list(simulado.questoes.order_by("ordem", "criado_em"))
        atual = next(questao for questao in questoes if str(questao.pk) == str(questao_pk))
        indice = questoes.index(atual)
        novo_indice = indice - 1 if direcao == "subir" else indice + 1
        if 0 <= novo_indice < len(questoes):
            outra = questoes[novo_indice]
            atual.ordem, outra.ordem = outra.ordem, atual.ordem
            atual.save(update_fields=["ordem"])
            outra.save(update_fields=["ordem"])
    except (StopIteration, ValidationError) as exc:
        messages.error(request, exc or "Não foi possível alterar a ordem.")
    return redirect("simulados_admin:admin_simulado_questoes", pk=simulado.pk)


@staff_required
def admin_resultados_simulado(request, pk):
    simulado = get_object_or_404(Simulado, pk=pk)
    tentativas = simulado.tentativas.select_related("usuario").order_by("-iniciada_em")
    paginator = Paginator(tentativas, 15)
    return render(request, "simulados/admin_resultados_lista.html", {"simulado": simulado, "page_obj": paginator.get_page(request.GET.get("page")), "active": "admin_simulados"})


@staff_required
def admin_resultado_detalhe(request, tentativa_pk):
    tentativa = get_object_or_404(TentativaSimulado.objects.select_related("usuario", "simulado"), pk=tentativa_pk)
    return render(request, "simulados/admin_resultado_detalhe.html", {"tentativa": tentativa, "diagnostico": diagnostico_tentativa(tentativa), "active": "admin_simulados"})
