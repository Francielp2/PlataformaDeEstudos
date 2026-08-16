from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import PerfilEstudante


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            raise ValidationError("Este e-mail já está cadastrado.")
        return email

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
    etapa_escolar = forms.ChoiceField(
        label="Etapa escolar",
        choices=[("", "---------")] + list(PerfilEstudante.EtapaEscolar.choices),
        required=False,
    )
    is_active = forms.BooleanField(label="Usuário ativo", required=False)
    is_staff = forms.BooleanField(label="Usuário administrativo", required=False)
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

    def __init__(
        self,
        *args,
        usuario=None,
        usuario_logado=None,
        criando=False,
        **kwargs,
    ):
        self.usuario = usuario
        self.usuario_logado = usuario_logado
        self.criando = criando
        super().__init__(*args, **kwargs)
        if criando:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        if self.usuario and self.usuario_logado == self.usuario:
            self.fields["is_staff"].disabled = True
            self.fields["is_staff"].help_text = (
                "Você não pode remover seu próprio acesso administrativo."
            )
            self.fields["is_active"].disabled = True
            self.fields["is_active"].help_text = (
                "Você não pode desativar a própria conta."
            )
        if (
            self.usuario
            and self.usuario.is_superuser
            and self.usuario_logado
            and not self.usuario_logado.is_superuser
        ):
            self.fields["is_staff"].disabled = True
            self.fields["is_active"].disabled = True
            self.fields["email"].disabled = True
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

        if self.usuario and self.usuario_logado == self.usuario:
            if cleaned_data.get("is_staff") is False:
                self.add_error(
                    "is_staff",
                    "Você não pode remover seu próprio acesso administrativo.",
                )
            if cleaned_data.get("is_active") is False:
                self.add_error(
                    "is_active",
                    "Você não pode desativar a própria conta.",
                )

        if (
            self.usuario
            and self.usuario.is_superuser
            and self.usuario_logado
            and not self.usuario_logado.is_superuser
        ):
            if cleaned_data.get("is_active") != self.usuario.is_active:
                self.add_error(
                    "is_active",
                    "Apenas superusuários podem alterar o status de um superusuário.",
                )
            if cleaned_data.get("email") != self.usuario.email:
                self.add_error(
                    "email",
                    "Apenas superusuários podem alterar o e-mail de um superusuário.",
                )

        return cleaned_data


class PerfilEstudanteForm(CampoBootstrapMixin, forms.Form):
    first_name = forms.CharField(label="Primeiro nome", max_length=150)
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150,
        required=False,
    )
    etapa_escolar = forms.ChoiceField(
        label="Etapa escolar",
        choices=PerfilEstudante.EtapaEscolar.choices,
    )
    senha_atual = forms.CharField(
        label="Senha atual",
        required=False,
        strip=False,
        widget=forms.PasswordInput,
    )
    nova_senha1 = forms.CharField(
        label="Nova senha",
        required=False,
        strip=False,
        widget=forms.PasswordInput,
    )
    nova_senha2 = forms.CharField(
        label="Confirmação da nova senha",
        required=False,
        strip=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        senha_atual = cleaned_data.get("senha_atual")
        nova_senha1 = cleaned_data.get("nova_senha1")
        nova_senha2 = cleaned_data.get("nova_senha2")

        quer_alterar_senha = senha_atual or nova_senha1 or nova_senha2
        if not quer_alterar_senha:
            return cleaned_data

        if not senha_atual:
            self.add_error("senha_atual", "Informe sua senha atual.")
        elif self.usuario and not self.usuario.check_password(senha_atual):
            self.add_error("senha_atual", "Senha atual incorreta.")

        if not nova_senha1:
            self.add_error("nova_senha1", "Informe a nova senha.")
        if not nova_senha2:
            self.add_error("nova_senha2", "Confirme a nova senha.")
        elif nova_senha1 and nova_senha1 != nova_senha2:
            self.add_error("nova_senha2", "As senhas não coincidem.")

        if nova_senha1:
            try:
                validate_password(nova_senha1, self.usuario)
            except ValidationError as exc:
                self.add_error("nova_senha1", exc)

        return cleaned_data
