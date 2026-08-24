from django import forms
from django.forms import inlineformset_factory

from curriculo.models import Conteudo, Materia
from questoes.models import Questao

from .models import AlternativaSimulado, QuestaoSimulado, Simulado


class SimuladoForm(forms.ModelForm):
    class Meta:
        model = Simulado
        fields = (
            "titulo",
            "descricao",
            "tipo",
            "materia",
            "status",
            "tempo_limite",
            "ordem_exibicao",
        )
        labels = {
            "titulo": "Título",
            "descricao": "Descrição",
            "tipo": "Tipo",
            "materia": "Matéria",
            "status": "Status",
            "tempo_limite": "Tempo limite em minutos",
            "ordem_exibicao": "Ordem de exibição",
        }
        widgets = {"descricao": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, permitir_status=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["materia"].queryset = Materia.objects.order_by("ordem_exibicao", "nome")
        if not permitir_status:
            self.fields["status"].disabled = True
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class SelecionarQuestoesForm(forms.Form):
    questoes = forms.ModelMultipleChoiceField(
        label="Questões",
        queryset=Questao.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["questoes"].queryset = queryset or Questao.objects.none()


class QuestaoSimuladoForm(forms.ModelForm):
    codigo = forms.CharField(label="Código", required=False, max_length=40)
    conteudos = forms.ModelMultipleChoiceField(
        label="Conteúdos",
        queryset=Conteudo.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
    )
    conteudo_principal = forms.ModelChoiceField(
        label="Conteúdo principal",
        queryset=Conteudo.objects.none(),
        required=True,
    )
    salvar_no_banco = forms.BooleanField(
        label="Salvar também no banco de questões",
        required=False,
    )

    class Meta:
        model = QuestaoSimulado
        fields = (
            "codigo",
            "enunciado",
            "explicacao",
            "dificuldade",
            "tipo_fonte",
            "fonte_nome",
            "fonte_ano",
            "fonte_url",
        )
        labels = {
            "enunciado": "Enunciado",
            "explicacao": "Explicação",
            "dificuldade": "Dificuldade",
            "tipo_fonte": "Tipo de fonte",
            "fonte_nome": "Nome da fonte",
            "fonte_ano": "Ano",
            "fonte_url": "URL",
        }
        widgets = {
            "enunciado": forms.Textarea(attrs={"rows": 6}),
            "explicacao": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, simulado=None, **kwargs):
        super().__init__(*args, **kwargs)
        conteudos = Conteudo.objects.select_related("materia").order_by(
            "materia__ordem_exibicao",
            "materia__nome",
            "ordem_sugerida",
            "titulo",
        )
        if simulado and simulado.tipo == Simulado.TipoSimulado.POR_MATERIA:
            conteudos = conteudos.filter(materia=simulado.materia)
        self.fields["conteudos"].queryset = conteudos
        self.fields["conteudo_principal"].queryset = conteudos
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned_data = super().clean()
        conteudos = cleaned_data.get("conteudos")
        principal = cleaned_data.get("conteudo_principal")
        if principal and conteudos is not None and principal not in conteudos:
            self.add_error(
                "conteudo_principal",
                "O conteúdo principal deve estar entre os conteúdos selecionados.",
            )
        return cleaned_data


class AlternativaSimuladoForm(forms.ModelForm):
    class Meta:
        model = AlternativaSimulado
        fields = ("chave", "texto", "correta", "ordem")
        labels = {
            "chave": "Chave",
            "texto": "Texto",
            "correta": "Correta",
            "ordem": "Ordem",
        }
        widgets = {"texto": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ordem"].required = False
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

    def has_changed(self):
        if self.instance._state.adding and self.is_bound:
            valores = [
                self.data.get(self.add_prefix("chave"), "").strip(),
                self.data.get(self.add_prefix("texto"), "").strip(),
                self.data.get(self.add_prefix("ordem"), "").strip(),
                self.data.get(self.add_prefix("correta")),
            ]
            if not any(valores):
                return False
        return super().has_changed()


AlternativaSimuladoFormSet = inlineformset_factory(
    QuestaoSimulado,
    AlternativaSimulado,
    form=AlternativaSimuladoForm,
    extra=2,
    min_num=2,
    validate_min=True,
    can_delete=False,
)


class ImportarJsonForm(forms.Form):
    json_questoes = forms.CharField(
        label="JSON de questões",
        widget=forms.Textarea(attrs={"rows": 16, "class": "form-control font-monospace"}),
    )
    salvar_no_banco = forms.BooleanField(
        label="Salvar questões importadas também no banco de questões",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class ResponderSimuladoForm(forms.Form):
    alternativa = forms.ModelChoiceField(
        label="Alternativa",
        queryset=AlternativaSimulado.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        required=False,
    )

    def __init__(self, *args, questao=None, resposta=None, **kwargs):
        super().__init__(*args, **kwargs)
        if questao:
            self.fields["alternativa"].queryset = questao.alternativas.order_by("ordem")
            self.fields["alternativa"].label_from_instance = (
                lambda alternativa: f"{alternativa.chave}. {alternativa.texto}"
            )
        if resposta:
            self.initial["alternativa"] = resposta.alternativa_escolhida_id
