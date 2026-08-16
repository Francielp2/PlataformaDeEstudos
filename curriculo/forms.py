from django import forms

from .models import Conteudo, Materia


class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = ("nome", "descricao", "ordem_exibicao", "ativa")
        labels = {
            "nome": "Nome",
            "descricao": "Descrição",
            "ordem_exibicao": "Ordem de exibição",
            "ativa": "Matéria ativa",
        }
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class ConteudoForm(forms.ModelForm):
    class Meta:
        model = Conteudo
        fields = (
            "materia",
            "pai",
            "titulo",
            "resumo",
            "texto_estudo",
            "dificuldade",
            "ordem_sugerida",
            "status",
        )
        labels = {
            "materia": "Matéria",
            "pai": "Conteúdo pai",
            "titulo": "Título",
            "resumo": "Resumo",
            "texto_estudo": "Texto de estudo",
            "dificuldade": "Dificuldade",
            "ordem_sugerida": "Ordem sugerida",
            "status": "Status",
        }
        widgets = {
            "resumo": forms.Textarea(attrs={"rows": 3}),
            "texto_estudo": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["materia"].queryset = Materia.objects.order_by(
            "ordem_exibicao",
            "nome",
        )
        candidatos_pai = Conteudo.objects.select_related("materia").order_by(
            "materia__ordem_exibicao",
            "materia__nome",
            "ordem_sugerida",
            "titulo",
        )
        if self.instance and self.instance.pk:
            candidatos_pai = candidatos_pai.exclude(pk=self.instance.pk)
        self.fields["pai"].queryset = candidatos_pai

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")
