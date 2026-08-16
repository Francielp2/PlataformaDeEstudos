from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import (
    CadastroEstudanteForm,
    LoginForm,
    PerfilEstudanteForm,
    UsuarioAdminForm,
)
from .models import PerfilEstudante


MATERIAS = {
    "matematica": "Matemática",
    "fisica": "Física",
    "quimica": "Química",
}

FUNCIONALIDADES_ESTUDANTE = {
    "conteudos": "Conteúdos de estudo",
    "exercicios": "Exercícios",
    "fazer-simulado": "Fazer simulado",
    "meus-simulados": "Meus simulados",
    "minha-lista": "Minha lista",
    "desempenho": "Meu desempenho",
}

FUNCIONALIDADES_ADMIN = {
    "cadastrar-materia": "Cadastro de matérias",
    "conteudos": "Gerenciamento de conteúdos",
    "questoes": "Gerenciamento de questões",
    "simulados": "Gerenciamento de simulados",
}


def _redirect_seguro(request, fallback):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(fallback)


def _staff_required(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('usuarios:login')}?next={request.path}")
    if not request.user.is_staff:
        messages.error(request, "Acesso negado. Esta área é restrita à administração.")
        return HttpResponseForbidden("Acesso negado. Esta área é restrita à administração.")
    return None


def _criar_relacionamentos_usuario(usuario, dados, request=None):
    PerfilEstudante.objects.create(
        usuario=usuario,
        etapa_escolar=dados.get("etapa_escolar", ""),
    )


def _dados_iniciais_admin(usuario):
    perfil = getattr(usuario, "perfil_estudante", None)
    return {
        "first_name": usuario.first_name,
        "last_name": usuario.last_name,
        "email": usuario.email,
        "etapa_escolar": perfil.etapa_escolar if perfil else "",
        "is_active": usuario.is_active,
        "is_staff": usuario.is_staff,
    }


def cadastro(request):
    if request.user.is_authenticated:
        return redirect("usuarios:painel")

    form = CadastroEstudanteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        User = get_user_model()
        with transaction.atomic():
            usuario = User.objects.create_user(
                email=dados["email"],
                password=dados["password1"],
                first_name=dados["first_name"],
                last_name=dados["last_name"],
                is_staff=False,
                is_superuser=False,
                is_active=True,
            )
            _criar_relacionamentos_usuario(usuario, dados, request)
        messages.success(request, "Cadastro concluído. Entre com seu e-mail e senha.")
        return redirect("usuarios:login")

    return render(request, "usuarios/cadastro.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("usuarios:painel")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        if request.POST.get("next") or request.GET.get("next"):
            return _redirect_seguro(request, "usuarios:painel")
        return redirect("usuarios:painel")

    return render(
        request,
        "usuarios/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


@login_required(login_url="usuarios:login")
def logout_view(request):
    if request.method != "POST":
        return redirect("usuarios:painel")
    logout(request)
    messages.info(request, "Sessão encerrada.")
    return redirect("usuarios:login")


@login_required(login_url="usuarios:login")
def painel(request):
    if request.user.is_staff:
        return redirect("usuarios:admin_painel")
    return redirect("usuarios:painel_estudante")


@login_required(login_url="usuarios:login")
def painel_estudante(request):
    perfil, _ = PerfilEstudante.objects.get_or_create(usuario=request.user)
    return render(
        request,
        "usuarios/painel_estudante.html",
        {"perfil": perfil, "active": "inicio"},
    )


@login_required(login_url="usuarios:login")
def perfil(request):
    perfil_obj, _ = PerfilEstudante.objects.get_or_create(usuario=request.user)
    initial = {
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
        "etapa_escolar": perfil_obj.etapa_escolar,
    }
    form = PerfilEstudanteForm(
        request.POST or None,
        initial=initial,
        usuario=request.user,
    )
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        with transaction.atomic():
            request.user.first_name = dados["first_name"]
            request.user.last_name = dados["last_name"]
            request.user.save(update_fields=["first_name", "last_name"])
            perfil_obj.etapa_escolar = dados["etapa_escolar"]
            perfil_obj.save(update_fields=["etapa_escolar", "atualizado_em"])
        messages.success(request, "Perfil atualizado.")
        return redirect("usuarios:perfil")

    return render(
        request,
        "usuarios/perfil.html",
        {"form": form, "perfil": perfil_obj, "active": "perfil"},
    )


@login_required(login_url="usuarios:login")
def materias(request):
    return render(
        request,
        "paginas/materias.html",
        {"materias": MATERIAS, "active": "materias"},
    )


@login_required(login_url="usuarios:login")
def materia_detalhe(request, slug):
    titulo = MATERIAS.get(slug)
    if not titulo:
        raise Http404("Matéria não encontrada.")
    return render(
        request,
        "paginas/materia_detalhe.html",
        {"titulo": titulo, "active": "materias"},
    )


@login_required(login_url="usuarios:login")
def funcionalidade_futura(request, slug):
    titulo = FUNCIONALIDADES_ESTUDANTE.get(slug)
    if not titulo:
        raise Http404("Funcionalidade não encontrada.")
    return render(
        request,
        "paginas/pagina_em_breve.html",
        {"titulo": titulo, "active": slug},
    )


def _render_admin(request, template, context=None):
    bloqueio = _staff_required(request)
    if bloqueio:
        return bloqueio
    contexto = context or {}
    return render(request, template, contexto)


def admin_painel(request):
    bloqueio = _staff_required(request)
    if bloqueio:
        return bloqueio

    User = get_user_model()
    contexto = {
        "total_usuarios": User.objects.count(),
        "total_estudantes": User.objects.filter(is_staff=False).count(),
        "total_staff": User.objects.filter(is_staff=True).count(),
        "total_ativos": User.objects.filter(is_active=True).count(),
        "total_inativos": User.objects.filter(is_active=False).count(),
        "cadastros_recentes": User.objects.order_by("-date_joined")[:5],
        "active": "admin_painel",
    }
    return render(request, "usuarios/painel_admin.html", contexto)


def admin_funcionalidade_futura(request, slug):
    titulo = FUNCIONALIDADES_ADMIN.get(slug)
    if not titulo:
        raise Http404("Funcionalidade não encontrada.")
    return _render_admin(
        request,
        "paginas/pagina_em_breve.html",
        {"titulo": titulo, "active": slug},
    )


def admin_usuarios_lista(request):
    bloqueio = _staff_required(request)
    if bloqueio:
        return bloqueio

    User = get_user_model()
    busca = request.GET.get("q", "").strip()
    usuarios = User.objects.select_related(
        "perfil_estudante"
    ).order_by("-date_joined")
    if busca:
        usuarios = usuarios.filter(
            Q(first_name__icontains=busca)
            | Q(last_name__icontains=busca)
            | Q(email__icontains=busca)
        )

    paginator = Paginator(usuarios, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "administracao/usuarios_lista.html",
        {"page_obj": page_obj, "busca": busca, "active": "admin_usuarios"},
    )


def admin_usuario_detalhe(request, pk):
    bloqueio = _staff_required(request)
    if bloqueio:
        return bloqueio

    usuario = get_object_or_404(get_user_model(), pk=pk)
    perfil_obj = getattr(usuario, "perfil_estudante", None)
    return render(
        request,
        "administracao/usuario_detalhe.html",
        {
            "usuario_obj": usuario,
            "perfil": perfil_obj,
            "active": "admin_usuarios",
        },
    )


def admin_usuario_criar(request):
    bloqueio = _staff_required(request)
    if bloqueio:
        return bloqueio

    initial = {
        "is_active": True,
    }
    form = UsuarioAdminForm(request.POST or None, initial=initial, criando=True)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        User = get_user_model()
        with transaction.atomic():
            usuario = User.objects.create_user(
                email=dados["email"],
                password=dados["password1"],
                first_name=dados["first_name"],
                last_name=dados["last_name"],
                is_active=dados["is_active"],
                is_staff=dados["is_staff"],
                is_superuser=False,
            )
            _criar_relacionamentos_usuario(usuario, dados)
        messages.success(request, "Usuário criado.")
        return redirect("usuarios:admin_usuario_detalhe", pk=usuario.pk)

    return render(
        request,
        "administracao/usuario_form.html",
        {"form": form, "titulo": "Criar usuário", "active": "admin_usuarios"},
    )


def admin_usuario_editar(request, pk):
    bloqueio = _staff_required(request)
    if bloqueio:
        return bloqueio

    usuario = get_object_or_404(get_user_model(), pk=pk)
    form = UsuarioAdminForm(
        request.POST or None,
        initial=_dados_iniciais_admin(usuario),
        usuario=usuario,
    )
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        with transaction.atomic():
            usuario.first_name = dados["first_name"]
            usuario.last_name = dados["last_name"]
            usuario.email = dados["email"]
            usuario.is_active = dados["is_active"]
            if not usuario.is_superuser or request.user.is_superuser:
                usuario.is_staff = dados["is_staff"]
            usuario.save()

            perfil_obj, _ = PerfilEstudante.objects.get_or_create(usuario=usuario)
            perfil_obj.etapa_escolar = dados["etapa_escolar"]
            perfil_obj.save()
        messages.success(request, "Usuário atualizado.")
        return redirect("usuarios:admin_usuario_detalhe", pk=usuario.pk)

    return render(
        request,
        "administracao/usuario_form.html",
        {"form": form, "titulo": "Editar usuário", "active": "admin_usuarios"},
    )


def admin_usuario_ativar(request, pk):
    bloqueio = _staff_required(request)
    if bloqueio:
        return bloqueio

    usuario = get_object_or_404(get_user_model(), pk=pk)
    if request.method == "POST":
        if usuario == request.user:
            messages.error(request, "Você não pode alterar o status da própria conta.")
        else:
            usuario.is_active = not usuario.is_active
            usuario.save(update_fields=["is_active"])
            messages.success(request, "Status do usuário atualizado.")
        return redirect("usuarios:admin_usuarios_lista")
    return render(
        request,
        "administracao/usuario_confirmar_ativacao.html",
        {"usuario_obj": usuario, "active": "admin_usuarios"},
    )


def admin_usuario_excluir(request, pk):
    bloqueio = _staff_required(request)
    if bloqueio:
        return bloqueio

    usuario = get_object_or_404(get_user_model(), pk=pk)
    if request.method == "POST":
        if usuario == request.user:
            messages.error(request, "Você não pode excluir a própria conta.")
            return redirect("usuarios:admin_usuario_detalhe", pk=usuario.pk)
        if usuario.is_superuser and not request.user.is_superuser:
            messages.error(request, "Apenas superusuários podem excluir superusuários.")
            return redirect("usuarios:admin_usuario_detalhe", pk=usuario.pk)
        try:
            usuario.delete()
        except ProtectedError:
            messages.error(
                request,
                "Não foi possível excluir: existem dados protegidos relacionados.",
            )
            return redirect("usuarios:admin_usuario_detalhe", pk=usuario.pk)
        messages.success(request, "Usuário excluído.")
        return redirect("usuarios:admin_usuarios_lista")

    return render(
        request,
        "administracao/usuario_confirmar_exclusao.html",
        {"usuario_obj": usuario, "active": "admin_usuarios"},
    )
