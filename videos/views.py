import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from curriculo.models import Conteudo, Materia
from curriculo.views import staff_required

from . import youtube
from .forms import ImportarVideosJsonForm, VideoCriarForm, VideoEditarForm
from .importacao_json import importar_videos_json
from .models import SessaoVideo, VideoConteudo
from .services import aplicar_metadados, registrar_progresso, validar_dados_progresso


TAMANHO_MAXIMO_CORPO_PROGRESSO = 20 * 1024
STATUS_VIDEO = {"", "ativos", "inativos"}


def _uuid_valido(valor):
    try:
        uuid.UUID(str(valor))
    except ValueError:
        return False
    return True


def _erro_json(mensagem, status):
    return JsonResponse({"erro": mensagem}, status=status)


@require_POST
def registrar_progresso_video(request, pk):
    if not request.user.is_authenticated:
        return _erro_json("Autenticação necessária.", 401)
    if len(request.body) > TAMANHO_MAXIMO_CORPO_PROGRESSO:
        return _erro_json("Corpo da requisição muito grande.", 400)
    try:
        dados = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _erro_json("JSON inválido.", 400)

    video = get_object_or_404(
        VideoConteudo.objects.select_related("conteudo"),
        pk=pk,
        ativo=True,
        conteudo__status=Conteudo.StatusConteudo.PUBLICADO,
        conteudo__materia__ativa=True,
    )
    try:
        resultado = registrar_progresso(video, request.user, validar_dados_progresso(dados))
    except ValidationError as exc:
        return _erro_json(exc.messages[0], 400)
    return JsonResponse(resultado)


@login_required(login_url="usuarios:login")
def historico(request):
    materia_slug = request.GET.get("materia", "").strip()
    sessoes = SessaoVideo.objects.filter(usuario=request.user).select_related(
        "video",
        "video__conteudo",
        "video__conteudo__materia",
    )
    if materia_slug:
        sessoes = sessoes.filter(video__conteudo__materia__slug=materia_slug)

    paginator = Paginator(sessoes, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    query_params.pop("page", None)
    materias = Materia.objects.filter(
        conteudos__videos__sessoes__usuario=request.user,
    ).distinct().order_by("ordem_exibicao", "nome")
    return render(
        request,
        "videos/historico.html",
        {
            "page_obj": page_obj,
            "materias": materias,
            "materia_slug": materia_slug,
            "querystring": query_params.urlencode(),
            "active": "historico-videos",
        },
    )


@staff_required
def admin_videos_lista(request):
    busca = request.GET.get("q", "").strip()
    materia_slug = request.GET.get("materia", "").strip()
    status = request.GET.get("status", "").strip()
    if status not in STATUS_VIDEO:
        status = ""

    videos = VideoConteudo.objects.select_related("conteudo", "conteudo__materia").order_by(
        "conteudo__materia__ordem_exibicao",
        "conteudo__materia__nome",
        "conteudo__titulo",
        "ordem",
        "criado_em",
    )
    if busca:
        videos = videos.filter(
            Q(titulo__icontains=busca)
            | Q(canal_nome__icontains=busca)
            | Q(youtube_id__icontains=busca)
            | Q(conteudo__titulo__icontains=busca)
        )
    if materia_slug:
        videos = videos.filter(conteudo__materia__slug=materia_slug)
    if status == "ativos":
        videos = videos.filter(ativo=True)
    elif status == "inativos":
        videos = videos.filter(ativo=False)

    paginator = Paginator(videos, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(
        request,
        "videos/admin_videos_lista.html",
        {
            "page_obj": page_obj,
            "busca": busca,
            "materia_slug": materia_slug,
            "status": status,
            "materias": Materia.objects.order_by("ordem_exibicao", "nome"),
            "querystring": query_params.urlencode(),
            "total_encontrado": paginator.count,
            "active": "admin_videos",
        },
    )


@staff_required
def admin_video_criar(request):
    initial = {}
    conteudo_pk = request.GET.get("conteudo")
    if conteudo_pk:
        conteudo = Conteudo.objects.filter(pk=conteudo_pk).first() if _uuid_valido(conteudo_pk) else None
        if conteudo:
            initial["conteudo"] = conteudo
    form = VideoCriarForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        video = form.save(commit=False)
        video.youtube_id = form.cleaned_data["url"]
        aplicar_metadados(video, form.metadados)
        video.criado_por = request.user
        video.full_clean()
        video.save()
        messages.success(request, "Vídeo cadastrado com sucesso.")
        return redirect("videos_admin:detalhe", pk=video.pk)

    voltar_url = reverse("videos_admin:lista")
    if initial.get("conteudo"):
        voltar_url = reverse("curriculo_admin:admin_conteudo_detalhe", args=[initial["conteudo"].pk])
    return render(
        request,
        "videos/admin_video_form.html",
        {
            "form": form,
            "titulo": "Novo vídeo",
            "criando": True,
            "active": "admin_videos",
            "voltar_url": voltar_url,
        },
    )


@staff_required
@require_GET
def admin_video_preview(request):
    try:
        youtube_id = youtube.extrair_youtube_id(request.GET.get("url", ""))
        metadados = youtube.buscar_metadados_youtube(youtube_id)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "erro": exc.messages[0]})
    return JsonResponse({"ok": True, "youtube_id": youtube_id, **metadados})


@staff_required
def admin_video_detalhe(request, pk):
    video = get_object_or_404(
        VideoConteudo.objects.select_related("conteudo", "conteudo__materia", "criado_por"),
        pk=pk,
    )
    numeros = video.progressos.aggregate(
        iniciaram=Count("id"),
        segundos_assistidos=Sum("segundos_assistidos_total"),
    )
    return render(
        request,
        "videos/admin_video_detalhe.html",
        {"video": video, **numeros, "active": "admin_videos"},
    )


@staff_required
def admin_video_editar(request, pk):
    video = get_object_or_404(VideoConteudo, pk=pk)
    form = VideoEditarForm(request.POST or None, instance=video)
    if request.method == "POST" and form.is_valid():
        video = form.save(commit=False)
        video.full_clean()
        video.save()
        messages.success(request, "Vídeo atualizado com sucesso.")
        return redirect("videos_admin:detalhe", pk=video.pk)
    return render(
        request,
        "videos/admin_video_form.html",
        {
            "form": form,
            "titulo": "Editar vídeo",
            "video": video,
            "criando": False,
            "active": "admin_videos",
            "voltar_url": reverse("videos_admin:detalhe", args=[pk]),
        },
    )


@staff_required
@require_POST
def admin_video_alternar_status(request, pk):
    video = get_object_or_404(VideoConteudo, pk=pk)
    video.ativo = not video.ativo
    video.save(update_fields=["ativo", "atualizado_em"])
    if video.ativo:
        messages.success(request, "Vídeo ativado com sucesso.")
    else:
        messages.success(request, "Vídeo desativado. O histórico dos estudantes foi preservado.")
    return redirect("videos_admin:detalhe", pk=video.pk)


@staff_required
@require_POST
def admin_video_atualizar_dados(request, pk):
    video = get_object_or_404(VideoConteudo, pk=pk)
    try:
        metadados = youtube.buscar_metadados_youtube(video.youtube_id)
    except ValidationError as exc:
        mensagem = exc.messages[0]
        if video.ativo:
            mensagem += " Se o vídeo não estiver mais disponível, considere desativá-lo."
        messages.error(request, mensagem)
        return redirect("videos_admin:detalhe", pk=video.pk)
    aplicar_metadados(video, metadados)
    video.full_clean()
    video.save()
    messages.success(request, "Dados do YouTube atualizados.")
    return redirect("videos_admin:detalhe", pk=video.pk)


@staff_required
def admin_importar_json(request):
    form = ImportarVideosJsonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            videos = importar_videos_json(form.cleaned_data["json_videos"], request.user)
            messages.success(
                request,
                f"Importação concluída. {len(videos)} vídeo(s) cadastrado(s) com sucesso.",
            )
            return redirect("videos_admin:lista")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "videos/admin_importar_json.html",
        {"form": form, "active": "admin_videos"},
    )
