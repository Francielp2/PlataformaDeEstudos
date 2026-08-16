from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ConteudoForm, MateriaForm
from .models import Conteudo, Materia
from estudos.views import ids_organizacao_usuario


STATUS_MATERIA = {"", "ativas", "inativas"}
STATUS_CONTEUDO = {choice.value for choice in Conteudo.StatusConteudo} | {""}
DIFICULDADES_CONTEUDO = {choice.value for choice in Conteudo.DificuldadeConteudo} | {""}


def staff_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('usuarios:login')}?next={request.path}")
        if not request.user.is_staff:
            messages.error(request, "Acesso negado. Esta área é restrita à administração.")
            return HttpResponseForbidden("Acesso negado. Esta área é restrita à administração.")
        return view_func(request, *args, **kwargs)

    return wrapper


@login_required(login_url="usuarios:login")
def materias_lista(request):
    materias = Materia.objects.filter(ativa=True)
    return render(
        request,
        "curriculo/materias_lista.html",
        {
            "materias": materias,
            "active": "materias",
            **ids_organizacao_usuario(request.user),
        },
    )


@login_required(login_url="usuarios:login")
def materia_detalhe(request, slug):
    materia = get_object_or_404(Materia, slug=slug, ativa=True)
    conteudos_raiz = (
        Conteudo.objects.filter(
            materia=materia,
            pai__isnull=True,
            status=Conteudo.StatusConteudo.PUBLICADO,
        )
        .prefetch_related(
            Prefetch(
                "subconteudos",
                queryset=Conteudo.objects.filter(
                    status=Conteudo.StatusConteudo.PUBLICADO,
                ).order_by("ordem_sugerida", "titulo"),
            )
        )
        .order_by("ordem_sugerida", "titulo")
    )
    subconteudos_publicados = Conteudo.objects.filter(
        materia=materia,
        pai__isnull=False,
        status=Conteudo.StatusConteudo.PUBLICADO,
    ).select_related("pai")
    conteudos_sem_pai_publicado = subconteudos_publicados.exclude(
        pai__status=Conteudo.StatusConteudo.PUBLICADO
    )
    return render(
        request,
        "curriculo/materia_detalhe.html",
        {
            "materia": materia,
            "conteudos_raiz": conteudos_raiz,
            "conteudos_sem_pai_publicado": conteudos_sem_pai_publicado,
            "active": "materias",
            **ids_organizacao_usuario(request.user),
        },
    )


@login_required(login_url="usuarios:login")
def conteudos_lista(request):
    busca = request.GET.get("q", "").strip()
    materia_slug = request.GET.get("materia", "").strip()
    dificuldade = request.GET.get("dificuldade", "").strip()
    if dificuldade not in DIFICULDADES_CONTEUDO:
        dificuldade = ""

    materias = Materia.objects.filter(ativa=True)
    conteudos = Conteudo.objects.filter(
        materia__ativa=True,
        status=Conteudo.StatusConteudo.PUBLICADO,
    ).select_related("materia", "pai")

    if busca:
        conteudos = conteudos.filter(titulo__icontains=busca)
    if materia_slug:
        conteudos = conteudos.filter(materia__slug=materia_slug)
    if dificuldade:
        conteudos = conteudos.filter(dificuldade=dificuldade)

    return render(
        request,
        "curriculo/conteudos_lista.html",
        {
            "conteudos": conteudos.order_by(
                "materia__ordem_exibicao",
                "materia__nome",
                "ordem_sugerida",
                "titulo",
            ),
            "materias": materias,
            "busca": busca,
            "materia_slug": materia_slug,
            "dificuldade": dificuldade,
            "dificuldades": Conteudo.DificuldadeConteudo,
            "active": "conteudos",
            **ids_organizacao_usuario(request.user),
        },
    )


@login_required(login_url="usuarios:login")
def conteudo_detalhe(request, materia_slug, conteudo_slug):
    materia = get_object_or_404(Materia, slug=materia_slug, ativa=True)
    conteudo = get_object_or_404(
        Conteudo.objects.select_related("materia", "pai"),
        materia=materia,
        slug=conteudo_slug,
        status=Conteudo.StatusConteudo.PUBLICADO,
    )
    subconteudos = Conteudo.objects.filter(
        materia=materia,
        pai=conteudo,
        status=Conteudo.StatusConteudo.PUBLICADO,
    ).order_by("ordem_sugerida", "titulo")
    return render(
        request,
        "curriculo/conteudo_detalhe.html",
        {
            "materia": materia,
            "conteudo": conteudo,
            "subconteudos": subconteudos,
            "active": "conteudos",
            **ids_organizacao_usuario(request.user),
        },
    )


@staff_required
def admin_materias_lista(request):
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if status not in STATUS_MATERIA:
        status = ""

    materias = Materia.objects.select_related("criado_por")
    if busca:
        materias = materias.filter(Q(nome__icontains=busca) | Q(slug__icontains=busca))
    if status == "ativas":
        materias = materias.filter(ativa=True)
    elif status == "inativas":
        materias = materias.filter(ativa=False)

    paginator = Paginator(materias, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request,
        "curriculo/admin_materias_lista.html",
        {
            "page_obj": page_obj,
            "busca": busca,
            "status": status,
            "querystring": query_params.urlencode(),
            "total_encontrado": paginator.count,
            "active": "admin_materias",
        },
    )


@staff_required
def admin_materia_criar(request):
    form = MateriaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        materia = form.save(commit=False)
        materia.criado_por = request.user
        materia.save()
        messages.success(request, "Matéria cadastrada com sucesso.")
        return redirect("curriculo_admin:admin_materia_detalhe", slug=materia.slug)

    return render(
        request,
        "curriculo/admin_materia_form.html",
        {"form": form, "titulo": "Criar matéria", "active": "admin_materias"},
    )


@staff_required
def admin_materia_detalhe(request, slug):
    materia = get_object_or_404(
        Materia.objects.select_related("criado_por"),
        slug=slug,
    )
    return render(
        request,
        "curriculo/admin_materia_detalhe.html",
        {"materia": materia, "active": "admin_materias"},
    )


@staff_required
def admin_materia_editar(request, slug):
    materia = get_object_or_404(Materia, slug=slug)
    criado_por_original = materia.criado_por
    form = MateriaForm(request.POST or None, instance=materia)
    if request.method == "POST" and form.is_valid():
        materia = form.save(commit=False)
        materia.criado_por = criado_por_original
        materia.save()
        messages.success(request, "Matéria atualizada com sucesso.")
        return redirect("curriculo_admin:admin_materia_detalhe", slug=materia.slug)

    return render(
        request,
        "curriculo/admin_materia_form.html",
        {"form": form, "titulo": "Editar matéria", "active": "admin_materias"},
    )


@require_POST
@staff_required
def admin_materia_alternar_status(request, slug):
    materia = get_object_or_404(Materia, slug=slug)
    materia.ativa = not materia.ativa
    materia.save(update_fields=["ativa", "atualizado_em"])
    if materia.ativa:
        messages.success(request, "Matéria ativada com sucesso.")
    else:
        messages.success(request, "Matéria desativada com sucesso.")
    return redirect("curriculo_admin:admin_materias_lista")


@staff_required
def admin_conteudos_lista(request):
    busca = request.GET.get("q", "").strip()
    materia_slug = request.GET.get("materia", "").strip()
    status = request.GET.get("status", "").strip()
    dificuldade = request.GET.get("dificuldade", "").strip()
    if status not in STATUS_CONTEUDO:
        status = ""
    if dificuldade not in DIFICULDADES_CONTEUDO:
        dificuldade = ""

    materias = Materia.objects.order_by("ordem_exibicao", "nome")
    conteudos = Conteudo.objects.select_related("materia", "pai", "criado_por").order_by(
        "materia__ordem_exibicao",
        "materia__nome",
        "ordem_sugerida",
        "titulo",
    )
    if busca:
        conteudos = conteudos.filter(
            Q(titulo__icontains=busca)
            | Q(slug__icontains=busca)
            | Q(materia__nome__icontains=busca)
        )
    if materia_slug:
        conteudos = conteudos.filter(materia__slug=materia_slug)
    if status:
        conteudos = conteudos.filter(status=status)
    if dificuldade:
        conteudos = conteudos.filter(dificuldade=dificuldade)

    paginator = Paginator(conteudos, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request,
        "curriculo/admin_conteudos_lista.html",
        {
            "page_obj": page_obj,
            "materias": materias,
            "busca": busca,
            "materia_slug": materia_slug,
            "status": status,
            "dificuldade": dificuldade,
            "status_choices": Conteudo.StatusConteudo,
            "dificuldades": Conteudo.DificuldadeConteudo,
            "querystring": query_params.urlencode(),
            "total_encontrado": paginator.count,
            "active": "admin_conteudos",
        },
    )


@staff_required
def admin_conteudo_criar(request):
    form = ConteudoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        conteudo = form.save(commit=False)
        conteudo.criado_por = request.user
        conteudo.save()
        messages.success(request, "Conteúdo cadastrado com sucesso.")
        return redirect(
            "curriculo_admin:admin_conteudo_detalhe",
            pk=conteudo.pk,
        )

    return render(
        request,
        "curriculo/admin_conteudo_form.html",
        {"form": form, "titulo": "Criar conteúdo", "active": "admin_conteudos"},
    )


@staff_required
def admin_conteudo_detalhe(request, pk):
    conteudo = get_object_or_404(
        Conteudo.objects.select_related("materia", "pai", "criado_por"),
        pk=pk,
    )
    return render(
        request,
        "curriculo/admin_conteudo_detalhe.html",
        {"conteudo": conteudo, "active": "admin_conteudos"},
    )


@staff_required
def admin_conteudo_editar(request, pk):
    conteudo = get_object_or_404(Conteudo, pk=pk)
    criado_por_original = conteudo.criado_por
    form = ConteudoForm(request.POST or None, instance=conteudo)
    if request.method == "POST" and form.is_valid():
        conteudo = form.save(commit=False)
        conteudo.criado_por = criado_por_original
        conteudo.save()
        messages.success(request, "Conteúdo atualizado com sucesso.")
        return redirect(
            "curriculo_admin:admin_conteudo_detalhe",
            pk=conteudo.pk,
        )

    return render(
        request,
        "curriculo/admin_conteudo_form.html",
        {"form": form, "titulo": "Editar conteúdo", "active": "admin_conteudos"},
    )


@require_POST
@staff_required
def admin_conteudo_alterar_status(request, pk, status):
    if status not in {choice.value for choice in Conteudo.StatusConteudo}:
        messages.error(request, "Status de conteúdo inválido.")
        return redirect("curriculo_admin:admin_conteudos_lista")

    conteudo = get_object_or_404(Conteudo, pk=pk)
    conteudo.status = status
    conteudo.save(update_fields=["status", "atualizado_em"])
    mensagens = {
        Conteudo.StatusConteudo.RASCUNHO: "Conteúdo retornado para rascunho.",
        Conteudo.StatusConteudo.PUBLICADO: "Conteúdo publicado com sucesso.",
        Conteudo.StatusConteudo.ARQUIVADO: "Conteúdo arquivado com sucesso.",
    }
    messages.success(request, mensagens[status])
    return redirect("curriculo_admin:admin_conteudos_lista")
