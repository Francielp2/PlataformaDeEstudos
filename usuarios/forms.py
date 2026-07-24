from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import PerfilEstudante, PreferenciaUsuario


class CampoBootstrapMixin:
    def _aplicar_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class LoginForm(CampoBootstrapMixin, AuthenticationForm):
    username = forms.EmailField(label="E-mail")

    error_messages = {
        "invalid_login": "E-mail ou senha inválidos.",
        "inactive": "Esta conta está inativa.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()


class CadastroEstudanteForm(CampoBootstrapMixin, forms.Form):
    first_name = forms.CharField(label="Primeiro nome", max_length=150)
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150,
        required=False,
    )
    email = forms.EmailField(label="E-mail")
    apelido_ranking = forms.CharField(label="Apelido para ranking", max_length=50)
    etapa_escolar = forms.ChoiceField(
        label="Etapa escolar",
        choices=PerfilEstudante.EtapaEscolar.choices,
    )
    password1 = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Confirmação de senha",
        strip=False,
        widget=forms.PasswordInput,
    )
    aceite_privacidade = forms.BooleanField(
        label="Li e aceito os termos e a política de privacidade.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            raise ValidationError("Este e-mail já está cadastrado.")
        return email

    def clean_apelido_ranking(self):
        apelido = self.cleaned_data["apelido_ranking"].strip()
        if PerfilEstudante.objects.filter(apelido_ranking__iexact=apelido).exists():
            raise ValidationError("Este apelido já está cadastrado.")
        return apelido

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "As senhas não coincidem.")

        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)

        return cleaned_data


class UsuarioAdminForm(CampoBootstrapMixin, forms.Form):
    first_name = forms.CharField(label="Primeiro nome", max_length=150)
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150,
        required=False,
    )
    email = forms.EmailField(label="E-mail")
    apelido_ranking = forms.CharField(
        label="Apelido para ranking",
        max_length=50,
        required=False,
    )
    etapa_escolar = forms.ChoiceField(
        label="Etapa escolar",
        choices=[("", "---------")] + list(PerfilEstudante.EtapaEscolar.choices),
        required=False,
    )
    is_active = forms.BooleanField(label="Usuário ativo", required=False)
    is_staff = forms.BooleanField(label="Usuário administrativo", required=False)
    exibir_ranking_publico = forms.BooleanField(
        label="Exibir no ranking público",
        required=False,
    )
    permitir_percentil_privado = forms.BooleanField(
        label="Permitir percentil privado",
        required=False,
    )
    notificacoes_email = forms.BooleanField(
        label="Receber notificações por e-mail",
        required=False,
    )
    dificuldade_preferida = forms.ChoiceField(
        label="Dificuldade preferida",
        choices=PreferenciaUsuario.DificuldadePreferida.choices,
    )
    password1 = forms.CharField(
        label="Senha",
        required=False,
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Confirmação de senha",
        required=False,
        strip=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, usuario=None, criando=False, **kwargs):
        self.usuario = usuario
        self.criando = criando
        super().__init__(*args, **kwargs)
        if criando:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        self._aplicar_bootstrap()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        queryset = User.objects.filter(email=email)
        if self.usuario:
            queryset = queryset.exclude(pk=self.usuario.pk)
        if queryset.exists():
            raise ValidationError("Este e-mail já está cadastrado.")
        return email

    def clean_apelido_ranking(self):
        apelido = self.cleaned_data.get("apelido_ranking", "").strip()
        queryset = PerfilEstudante.objects.filter(apelido_ranking__iexact=apelido)
        if self.usuario:
            queryset = queryset.exclude(usuario=self.usuario)
        if apelido and queryset.exists():
            raise ValidationError("Este apelido já está cadastrado.")
        return apelido

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if self.criando or password1 or password2:
            if password1 != password2:
                self.add_error("password2", "As senhas não coincidem.")
            if password1:
                try:
                    validate_password(password1, self.usuario)
                except ValidationError as exc:
                    self.add_error("password1", exc)

        if self.usuario and self.usuario.is_superuser:
            if cleaned_data.get("is_staff") is False:
                self.add_error(
                    "is_staff",
                    "Não é permitido remover staff de um superusuário aqui.",
                )

        return cleaned_data


class PerfilEstudanteForm(CampoBootstrapMixin, forms.Form):
    first_name = forms.CharField(label="Primeiro nome", max_length=150)
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150,
        required=False,
    )
    apelido_ranking = forms.CharField(label="Apelido para ranking", max_length=50)
    etapa_escolar = forms.ChoiceField(
        label="Etapa escolar",
        choices=PerfilEstudante.EtapaEscolar.choices,
    )
    dificuldade_preferida = forms.ChoiceField(
        label="Dificuldade preferida",
        choices=PreferenciaUsuario.DificuldadePreferida.choices,
    )
    exibir_ranking_publico = forms.BooleanField(
        label="Exibir no ranking público",
        required=False,
    )
    permitir_percentil_privado = forms.BooleanField(
        label="Permitir percentil privado",
        required=False,
    )

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean_apelido_ranking(self):
        apelido = self.cleaned_data["apelido_ranking"].strip()
        queryset = PerfilEstudante.objects.filter(apelido_ranking__iexact=apelido)
        if self.usuario:
            queryset = queryset.exclude(usuario=self.usuario)
        if queryset.exists():
            raise ValidationError("Este apelido já está cadastrado.")
        return apelido
