from django import forms

from .models import Materia


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
