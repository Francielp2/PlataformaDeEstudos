import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class GerenciadorUsuario(BaseUserManager):
    """Gerenciador para autenticação por e-mail."""

    use_in_migrations = True

    def _normalizar_email(self, email):
        email_normalizado = self.normalize_email(email)
        return email_normalizado.lower()

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("O e-mail é obrigatório."))

        email = self._normalizar_email(email)
        usuario = self.model(email=email, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superusuário deve ter is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superusuário deve ter is_superuser=True."))

        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(_("e-mail"), unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name"]

    objects = GerenciadorUsuario()

    class Meta:
        db_table = "usuarios_usuario"
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = Usuario.objects._normalizar_email(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class PerfilEstudante(models.Model):
    class EtapaEscolar(models.TextChoices):
        PRIMEIRO_ANO = "primeiro_ano", _("1º ano do Ensino Médio")
        SEGUNDO_ANO = "segundo_ano", _("2º ano do Ensino Médio")
        TERCEIRO_ANO = "terceiro_ano", _("3º ano do Ensino Médio")
        CURSINHO = "cursinho", _("Cursinho")
        OUTRO = "outro", _("Outro")

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil_estudante",
    )
    etapa_escolar = models.CharField(
        max_length=20,
        choices=EtapaEscolar.choices,
        blank=True,
    )
    criado_em = models.DateTimeField(default=timezone.now, editable=False)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "usuarios_perfil_estudante"
        verbose_name = "perfil de estudante"
        verbose_name_plural = "perfis de estudantes"

    def __str__(self):
        return str(self.usuario)
