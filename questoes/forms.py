from django import forms
from django.forms import inlineformset_factory

from curriculo.models import Conteudo, Materia

from .models import Alternativa, Questao


class QuestaoForm(forms.ModelForm):
    conteudos = forms.ModelMultipleChoiceField(
        label="Conteúdos",
        queryset=Conteudo.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    conteudo_principal = forms.ModelChoiceField(
        label="Conteúdo principal",
        queryset=Conteudo.objects.none(),
        required=False,
        empty_label="---------",
    )

    class Meta:
        model = Questao
        fields = (
            "codigo",
            "materia",
            "enunciado",
            "explicacao",
            "dificuldade",
            "tipo_fonte",
            "fonte_nome",
            "fonte_ano",
            "fonte_url",
            "status",
        )
        labels = {
            "codigo": "Código",
            "materia": "Matéria",
            "enunciado": "Enunciado",
            "explicacao": "Explicação",
            "dificuldade": "Dificuldade",
            "tipo_fonte": "Tipo de fonte",
            "fonte_nome": "Nome da fonte",
            "fonte_ano": "Ano da fonte",
            "fonte_url": "URL da fonte",
            "status": "Status",
        }
        widgets = {
            "enunciado": forms.Textarea(attrs={"rows": 6}),
            "explicacao": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["materia"].queryset = Materia.objects.order_by(
            "ordem_exibicao",
            "nome",
        )
        conteudos = Conteudo.objects.select_related("materia").order_by(
            "materia__ordem_exibicao",
            "materia__nome",
            "ordem_sugerida",
            "titulo",
        )
        self.fields["conteudos"].queryset = conteudos
        self.fields["conteudo_principal"].queryset = conteudos

        if self.instance and self.instance.pk:
            selecionados = self.instance.questao_conteudos.values_list(
                "conteudo_id",
                flat=True,
            )
            self.initial.setdefault("conteudos", list(selecionados))
            principal = self.instance.questao_conteudos.filter(principal=True).first()
            if principal:
                self.initial.setdefault("conteudo_principal", principal.conteudo_id)

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
        materia = cleaned_data.get("materia")
        conteudos = cleaned_data.get("conteudos")
        principal = cleaned_data.get("conteudo_principal")

        if materia and conteudos:
            invalidos = [
                conteudo for conteudo in conteudos if conteudo.materia_id != materia.id
            ]
            if invalidos:
                self.add_error(
                    "conteudos",
                    "Todos os conteúdos devem pertencer à matéria da questão.",
                )

        if principal and conteudos is not None and principal not in conteudos:
            self.add_error(
                "conteudo_principal",
                "O conteúdo principal deve estar entre os conteúdos selecionados.",
            )

        return cleaned_data


class AlternativaForm(forms.ModelForm):
    class Meta:
        model = Alternativa
        fields = ("chave", "texto", "correta", "ordem")
        labels = {
            "chave": "Chave",
            "texto": "Texto",
            "correta": "Correta",
            "ordem": "Ordem",
        }
        widgets = {
            "texto": forms.Textarea(attrs={"rows": 3}),
        }

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
            chave = self.data.get(self.add_prefix("chave"), "").strip()
            texto = self.data.get(self.add_prefix("texto"), "").strip()
            ordem = self.data.get(self.add_prefix("ordem"), "").strip()
            correta = self.data.get(self.add_prefix("correta"))
            if not any([chave, texto, ordem, correta]):
                return False
        return super().has_changed()

    def clean(self):
        cleaned_data = super().clean()
        chave = cleaned_data.get("chave")
        texto = cleaned_data.get("texto")
        correta = cleaned_data.get("correta")
        ordem = cleaned_data.get("ordem")
        if (chave or texto or correta) and ordem is None:
            self.add_error("ordem", "Informe a ordem da alternativa.")
        return cleaned_data


AlternativaFormSet = inlineformset_factory(
    Questao,
    Alternativa,
    form=AlternativaForm,
    extra=5,
    min_num=2,
    validate_min=False,
    can_delete=False,
)


class ResponderQuestaoForm(forms.Form):
    alternativa = forms.ModelChoiceField(
        label="Alternativa",
        queryset=Alternativa.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
    )

    def __init__(self, *args, questao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if questao:
            self.fields["alternativa"].queryset = questao.alternativas.order_by("ordem")
            self.fields["alternativa"].label_from_instance = (
                lambda alternativa: f"{alternativa.chave}. {alternativa.texto}"
            )
