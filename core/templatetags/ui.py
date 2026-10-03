"""Filtros e tags de apresentação compartilhados pelos templates.

Só decidem aparência (ícone, cor, atributos de acessibilidade); não mudam dados
nem regras do sistema.
"""

import unicodedata
import zlib

from django import template
from django.forms import CheckboxInput, CheckboxSelectMultiple, PasswordInput, RadioSelect, Textarea
from django.utils.html import format_html_join


register = template.Library()

TONS = ("tom-menta", "tom-ceu", "tom-sol", "tom-lilas", "tom-laranja", "tom-coral")

# Ícone e tom por palavra-chave do slug da matéria (o primeiro que casar vence).
VISUAL_MATERIAS = (
    (("matematica",), "bi-calculator", "tom-ceu"),
    (("fisica",), "bi-lightning-charge", "tom-sol"),
    (("quimica",), "bi-eyedropper", "tom-lilas"),
    (("biologia", "natureza"), "bi-flower1", "tom-menta"),
    (("historia",), "bi-hourglass-split", "tom-laranja"),
    (("geografia",), "bi-globe-americas", "tom-menta"),
    (("redacao",), "bi-pencil", "tom-coral"),
    (("literatura",), "bi-book-half", "tom-lilas"),
    (("portugues", "linguagens", "lingua-portuguesa"), "bi-chat-quote", "tom-coral"),
    (("ingles", "espanhol", "estrangeira"), "bi-translate", "tom-ceu"),
    (("filosofia",), "bi-lightbulb", "tom-sol"),
    (("sociologia", "humanas"), "bi-people", "tom-laranja"),
    (("artes", "arte"), "bi-palette", "tom-lilas"),
    (("educacao-fisica",), "bi-trophy", "tom-menta"),
)

DIFICULDADES = {
    "basic": ("tom-menta", "bi-reception-1"),
    "easy": ("tom-menta", "bi-reception-1"),
    "intermediate": ("tom-sol", "bi-reception-2"),
    "medium": ("tom-sol", "bi-reception-2"),
    "advanced": ("tom-coral", "bi-reception-4"),
    "hard": ("tom-coral", "bi-reception-4"),
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto or "")).encode("ascii", "ignore").decode()
    return texto.lower().replace(" ", "-")


@register.filter
def materia_visual(materia):
    """Ícone e tom de uma matéria (aceita a matéria, o slug ou o nome)."""
    chave = _normalizar(getattr(materia, "slug", None) or getattr(materia, "nome", None) or materia)
    for palavras, icone, tom in VISUAL_MATERIAS:
        if any(palavra in chave for palavra in palavras):
            return {"icone": icone, "tom": tom}
    if not chave:
        return {"icone": "bi-grid", "tom": "tom-neutro"}
    return {"icone": "bi-journal-bookmark", "tom": TONS[zlib.crc32(chave.encode()) % len(TONS)]}


@register.filter
def dificuldade_visual(valor):
    tom, icone = DIFICULDADES.get(str(valor), ("tom-neutro", "bi-reception-0"))
    return {"tom": tom, "icone": icone}


@register.filter
def coluna_campo(field):
    """Largura do campo na grade do formulário: textos longos ocupam a linha toda."""
    widget = field.field.widget
    if isinstance(widget, (Textarea, CheckboxSelectMultiple, RadioSelect)):
        return ""
    return "col-meio"


@register.filter
def eh_checkbox(field):
    return isinstance(field.field.widget, CheckboxInput)


@register.filter
def eh_senha(field):
    return isinstance(field.field.widget, PasswordInput)


@register.simple_tag
def widget(field, **attrs):
    """Renderiza o campo ligando ajuda e erros por aria-describedby."""
    descritores = []
    if field.help_text:
        descritores.append(f"{field.auto_id}_ajuda")
    if field.errors:
        descritores.append(f"{field.auto_id}_erro")
        attrs["aria-invalid"] = "true"
        classes = field.field.widget.attrs.get("class", "")
        attrs["class"] = f"{attrs.get('class', classes)} is-invalid".strip()
    if descritores:
        attrs["aria-describedby"] = " ".join(descritores)
    if field.field.required and not isinstance(field.field.widget, CheckboxInput):
        attrs.setdefault("required", True)
    return field.as_widget(attrs=attrs)


@register.filter
def iniciais(usuario):
    nome = (getattr(usuario, "first_name", "") or "").strip()
    sobrenome = (getattr(usuario, "last_name", "") or "").strip()
    if nome:
        return (nome[:1] + sobrenome[:1]).upper()
    return (getattr(usuario, "email", "") or "?")[:1].upper()


@register.simple_tag(takes_context=True)
def query_sem(context, *nomes):
    """Querystring atual sem os parâmetros informados (para 'remover filtro')."""
    params = context["request"].GET.copy()
    for nome in nomes:
        params.pop(nome, None)
    params.pop("page", None)
    texto = params.urlencode()
    return f"?{texto}" if texto else "?"


@register.simple_tag
def atributos(**attrs):
    return format_html_join(" ", '{}="{}"', attrs.items())
