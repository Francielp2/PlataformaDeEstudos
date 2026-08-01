from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import CadastroEstudanteForm, PerfilEstudanteForm, UsuarioAdminForm
from .models import PerfilEstudante


class UsuariosFluxoTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def dados_cadastro(self, **extra):
        dados = {
            "first_name": "Ana",
            "last_name": "Silva",
            "email": "ana@example.com",
            "etapa_escolar": PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
            "password1": "SenhaForte123",
            "password2": "SenhaForte123",
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
        PerfilEstudante.objects.create(usuario=usuario)
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
        self.assertEqual(
            usuario.perfil_estudante.etapa_escolar,
            PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
        )

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

    def test_login_bloqueia_usuario_inativo(self):
        self.criar_usuario("inativo@example.com", is_active=False)

        response = self.client.post(
            reverse("usuarios:login"),
            {"username": "inativo@example.com", "password": "SenhaForte123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-mail ou senha inválidos.")
        self.assertNotIn("_auth_user_id", self.client.session)

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

    def test_superusuario_tambem_e_identificado_como_administrador(self):
        admin = self.User.objects.create_superuser(
            email="super@example.com",
            password="SenhaForte123",
            first_name="Super",
        )

        self.client.force_login(admin)
        response = self.client.get(reverse("usuarios:painel"))

        self.assertRedirects(response, reverse("usuarios:admin_painel"))

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

    def test_edicao_de_perfil_atualiza_dados_basicos(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.post(
            reverse("usuarios:perfil"),
            {
                "first_name": "Maria",
                "last_name": "Souza",
                "etapa_escolar": PerfilEstudante.EtapaEscolar.CURSINHO,
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("usuarios:perfil"))
        estudante.refresh_from_db()
        estudante.perfil_estudante.refresh_from_db()
        self.assertEqual(estudante.first_name, "Maria")
        self.assertEqual(estudante.last_name, "Souza")
        self.assertEqual(
            estudante.perfil_estudante.etapa_escolar,
            PerfilEstudante.EtapaEscolar.CURSINHO,
        )

    def test_painel_cria_perfil_quando_usuario_antigo_nao_tem_perfil(self):
        estudante = self.User.objects.create_user(
            email="semperfil@example.com",
            password="SenhaForte123",
            first_name="Sem",
        )
        self.client.force_login(estudante)

        response = self.client.get(reverse("usuarios:painel_estudante"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(hasattr(estudante, "perfil_estudante"))

    def test_formularios_nao_possuem_campos_de_ranking_ou_recomendacao(self):
        campos_removidos = {
            "apelido_ranking",
            "exibir_ranking_publico",
            "permitir_percentil_privado",
            "dificuldade_preferida",
            "aceite_privacidade",
        }

        for form in (CadastroEstudanteForm(), PerfilEstudanteForm(), UsuarioAdminForm()):
            self.assertTrue(campos_removidos.isdisjoint(form.fields))

    def test_usuario_nao_possui_campos_de_privacidade_removidos(self):
        campos_usuario = {field.name for field in self.User._meta.get_fields()}

        self.assertNotIn("anonimizado_em", campos_usuario)
        self.assertNotIn("consentimentos_privacidade", campos_usuario)

    def test_administrador_nao_exclui_propria_conta(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("usuarios:admin_usuario_excluir", kwargs={"pk": admin.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.User.objects.filter(pk=admin.pk).exists())
