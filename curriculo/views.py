from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import MateriaForm
from .models import Materia


STATUS_MATERIA = {"", "ativas", "inativas"}


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
        {"materias": materias, "active": "materias"},
    )


@login_required(login_url="usuarios:login")
def materia_detalhe(request, slug):
    materia = get_object_or_404(Materia, slug=slug, ativa=True)
    return render(
        request,
        "curriculo/materia_detalhe.html",
        {"materia": materia, "active": "materias"},
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
