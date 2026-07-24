from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import PerfilEstudante, PreferenciaUsuario


class UsuariosFluxoTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def dados_cadastro(self, **extra):
        dados = {
            "first_name": "Ana",
            "last_name": "Silva",
            "email": "ana@example.com",
            "apelido_ranking": "anaenem",
            "etapa_escolar": PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
            "password1": "SenhaForte123",
            "password2": "SenhaForte123",
            "aceite_privacidade": "on",
        }
        dados.update(extra)
        return dados

    def criar_usuario(self, email, password="SenhaForte123", **extra):
        usuario = self.User.objects.create_user(
            email=email,
            password=password,
            first_name=extra.pop("first_name", "Usuário"),
            **extra,
        )
        PerfilEstudante.objects.create(usuario=usuario, apelido_ranking=email.split("@")[0])
        PreferenciaUsuario.objects.create(usuario=usuario)
        return usuario

    def test_cadastro_cria_usuario_comum(self):
        response = self.client.post(
            reverse("usuarios:cadastro"),
            self.dados_cadastro(),
        )

        self.assertRedirects(response, reverse("usuarios:login"))
        usuario = self.User.objects.get(email="ana@example.com")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertTrue(usuario.is_active)

    def test_cadastro_usa_senha_com_hash(self):
        self.client.post(reverse("usuarios:cadastro"), self.dados_cadastro())

        usuario = self.User.objects.get(email="ana@example.com")
        self.assertNotEqual(usuario.password, "SenhaForte123")
        self.assertTrue(usuario.check_password("SenhaForte123"))

    def test_cadastro_cria_perfil(self):
        self.client.post(reverse("usuarios:cadastro"), self.dados_cadastro())

        usuario = self.User.objects.get(email="ana@example.com")
        self.assertTrue(hasattr(usuario, "perfil_estudante"))
        self.assertEqual(usuario.perfil_estudante.apelido_ranking, "anaenem")

    def test_cadastro_cria_preferencias(self):
        self.client.post(reverse("usuarios:cadastro"), self.dados_cadastro())

        usuario = self.User.objects.get(email="ana@example.com")
        self.assertTrue(hasattr(usuario, "preferencias"))

    def test_login_estudante_redireciona_para_painel_estudante(self):
        self.criar_usuario("estudante@example.com")

        response = self.client.post(
            reverse("usuarios:login"),
            {"username": "estudante@example.com", "password": "SenhaForte123"},
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("usuarios:painel_estudante"),
            target_status_code=200,
        )

    def test_login_staff_redireciona_para_painel_administrativo(self):
        self.criar_usuario("admin@example.com", is_staff=True)

        response = self.client.post(
            reverse("usuarios:login"),
            {"username": "admin@example.com", "password": "SenhaForte123"},
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("usuarios:admin_painel"),
            target_status_code=200,
        )

    def test_estudante_nao_acessa_area_administrativa(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.get(reverse("usuarios:admin_painel"))

        self.assertEqual(response.status_code, 403)

    def test_usuario_nao_autenticado_nao_acessa_paineis_privados(self):
        response_estudante = self.client.get(reverse("usuarios:painel_estudante"))
        response_admin = self.client.get(reverse("usuarios:admin_painel"))

        self.assertEqual(response_estudante.status_code, 302)
        self.assertEqual(response_admin.status_code, 302)

    def test_administrador_consegue_listar_usuarios(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("estudante@example.com")
        self.client.force_login(admin)

        response = self.client.get(reverse("usuarios:admin_usuarios_lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "estudante@example.com")

    def test_estudante_nao_consegue_definir_is_staff_no_cadastro(self):
        dados = self.dados_cadastro(is_staff="on", is_superuser="on")

        self.client.post(reverse("usuarios:cadastro"), dados)

        usuario = self.User.objects.get(email="ana@example.com")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)

    def test_logout_encerra_sessao(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.post(reverse("usuarios:logout"), follow=True)

        self.assertRedirects(response, reverse("usuarios:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_administrador_nao_exclui_propria_conta(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("usuarios:admin_usuario_excluir", kwargs={"pk": admin.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.User.objects.filter(pk=admin.pk).exists())
