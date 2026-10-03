from django import forms
from django.core.exceptions import ValidationError

from curriculo.models import Conteudo

from . import youtube
from .models import VideoConteudo


def _conteudos_para_select():
    return Conteudo.objects.select_related("materia").order_by(
        "materia__ordem_exibicao",
        "materia__nome",
        "ordem_sugerida",
        "titulo",
    )


class _BootstrapMixin:
    def _aplicar_classes(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class VideoEditarForm(_BootstrapMixin, forms.ModelForm):
    """Campos que o admin pode alterar. Título, canal e link vêm do YouTube e não são editáveis."""

    class Meta:
        model = VideoConteudo
        fields = ("conteudo", "nota_curador", "ordem", "ativo")
        labels = {
            "conteudo": "Matéria - Conteúdo",
            "nota_curador": "Nota do curador",
            "ordem": "Ordem",
            "ativo": "Vídeo ativo",
        }
        help_texts = {
            "nota_curador": "Explique ao estudante por que este vídeo foi escolhido.",
        }
        widgets = {
            "nota_curador": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["conteudo"].queryset = _conteudos_para_select()
        self._aplicar_classes()

    def _youtube_id(self):
        return self.instance.youtube_id

    def clean(self):
        cleaned_data = super().clean()
        conteudo = cleaned_data.get("conteudo")
        youtube_id = self._youtube_id()
        if conteudo and youtube_id:
            duplicados = VideoConteudo.objects.filter(conteudo=conteudo, youtube_id=youtube_id)
            if self.instance.pk:
                duplicados = duplicados.exclude(pk=self.instance.pk)
            if duplicados.exists():
                raise ValidationError("Este vídeo já está cadastrado neste conteúdo.")
        return cleaned_data


class VideoCriarForm(VideoEditarForm):
    url = forms.CharField(
        label="Link do YouTube",
        max_length=500,
        help_text="Cole o link do vídeo. Título e canal são obtidos automaticamente do YouTube.",
    )

    field_order = ("conteudo", "url", "nota_curador", "ordem", "ativo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["url"].widget.attrs.update(
            {"placeholder": "https://www.youtube.com/watch?v=...", "class": "form-control"}
        )
        self.metadados = None

    def clean_url(self):
        return youtube.extrair_youtube_id(self.cleaned_data["url"])

    def _youtube_id(self):
        return self.cleaned_data.get("url")

    def clean(self):
        cleaned_data = super().clean()
        youtube_id = cleaned_data.get("url")
        if youtube_id and not self.errors:
            # A autoria é sempre consultada no servidor, nunca recebida do formulário.
            self.metadados = youtube.buscar_metadados_youtube(youtube_id)
            self.instance.youtube_id = youtube_id
        return cleaned_data


class ImportarVideosJsonForm(forms.Form):
    json_videos = forms.CharField(
        label="JSON de vídeos",
        widget=forms.Textarea(attrs={"rows": 16, "class": "form-control font-monospace"}),
    )
