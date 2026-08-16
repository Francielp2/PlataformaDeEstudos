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

    def dados_admin_usuario(self, usuario=None, **extra):
        dados = {
            "first_name": usuario.first_name if usuario else "Novo",
            "last_name": usuario.last_name if usuario else "Usuário",
            "email": usuario.email if usuario else "novo@example.com",
            "etapa_escolar": PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
            "is_active": "on",
            "password1": "",
            "password2": "",
        }
        if usuario and usuario.is_staff:
            dados["is_staff"] = "on"
        dados.update(extra)
        return dados

    def emails_da_listagem(self, response):
        return {usuario.email for usuario in response.context["page_obj"]}

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
        self.assertContains(response, "Você")

    def test_listagem_nao_exibe_acoes_de_status_ou_exclusao_para_usuario_atual(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.client.force_login(admin)

        response = self.client.get(reverse("usuarios:admin_usuarios_lista"))

        self.assertContains(response, "Você")
        self.assertNotContains(
            response,
            reverse("usuarios:admin_usuario_ativar", kwargs={"pk": admin.pk}),
        )
        self.assertNotContains(
            response,
            reverse("usuarios:admin_usuario_excluir", kwargs={"pk": admin.pk}),
        )

    def test_busca_encontra_trecho_do_primeiro_nome(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("pedro@example.com", first_name="Pedro", last_name="Mendes")
        self.criar_usuario("ana@example.com", first_name="Ana")
        self.client.force_login(admin)

        response = self.client.get(reverse("usuarios:admin_usuarios_lista"), {"q": "ped"})

        self.assertIn("pedro@example.com", self.emails_da_listagem(response))
        self.assertNotIn("ana@example.com", self.emails_da_listagem(response))

    def test_busca_encontra_trecho_do_sobrenome(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("pedro@example.com", first_name="Pedro", last_name="Mendes")
        self.criar_usuario("ana@example.com", first_name="Ana", last_name="Souza")
        self.client.force_login(admin)

        response = self.client.get(reverse("usuarios:admin_usuarios_lista"), {"q": "mend"})

        self.assertIn("pedro@example.com", self.emails_da_listagem(response))
        self.assertNotIn("ana@example.com", self.emails_da_listagem(response))

    def test_busca_encontra_trecho_do_email(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("pedro@gmail.com", first_name="Pedro")
        self.criar_usuario("ana@example.com", first_name="Ana")
        self.client.force_login(admin)

        response = self.client.get(reverse("usuarios:admin_usuarios_lista"), {"q": "gmail"})

        self.assertIn("pedro@gmail.com", self.emails_da_listagem(response))
        self.assertNotIn("ana@example.com", self.emails_da_listagem(response))

    def test_busca_e_case_insensitive(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("pedro@example.com", first_name="Pedro")
        self.client.force_login(admin)

        response = self.client.get(reverse("usuarios:admin_usuarios_lista"), {"q": "PED"})

        self.assertContains(response, "pedro@example.com")

    def test_busca_com_duas_palavras_em_campos_diferentes(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario(
            "pedro@example.com",
            first_name="Pedro Augusto",
            last_name="Mendes Azevedo",
        )
        self.criar_usuario("pedro.souza@example.com", first_name="Pedro", last_name="Souza")
        self.client.force_login(admin)

        response = self.client.get(
            reverse("usuarios:admin_usuarios_lista"),
            {"q": "Pedro Mendes"},
        )

        self.assertIn("pedro@example.com", self.emails_da_listagem(response))
        self.assertNotIn("pedro.souza@example.com", self.emails_da_listagem(response))

    def test_filtro_somente_estudantes(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("estudante@example.com")
        self.client.force_login(admin)

        response = self.client.get(
            reverse("usuarios:admin_usuarios_lista"),
            {"tipo": "estudante"},
        )

        self.assertIn("estudante@example.com", self.emails_da_listagem(response))
        self.assertNotIn("admin@example.com", self.emails_da_listagem(response))

    def test_filtro_somente_administradores(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("outro-admin@example.com", is_staff=True)
        superusuario = self.User.objects.create_superuser(
            email="super@example.com",
            password="SenhaForte123",
            first_name="Super",
        )
        self.client.force_login(admin)

        response = self.client.get(
            reverse("usuarios:admin_usuarios_lista"),
            {"tipo": "administrador"},
        )

        emails = self.emails_da_listagem(response)
        self.assertIn("outro-admin@example.com", emails)
        self.assertIn("admin@example.com", emails)
        self.assertNotIn(superusuario.email, emails)

    def test_filtro_somente_superusuarios(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        superusuario = self.User.objects.create_superuser(
            email="super@example.com",
            password="SenhaForte123",
            first_name="Super",
        )
        self.client.force_login(admin)

        response = self.client.get(
            reverse("usuarios:admin_usuarios_lista"),
            {"tipo": "superusuario"},
        )

        self.assertIn(superusuario.email, self.emails_da_listagem(response))
        self.assertNotIn("admin@example.com", self.emails_da_listagem(response))

    def test_filtro_somente_ativos(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("ativo@example.com")
        self.criar_usuario("inativo@example.com", is_active=False)
        self.client.force_login(admin)

        response = self.client.get(
            reverse("usuarios:admin_usuarios_lista"),
            {"status": "ativo"},
        )

        self.assertIn("ativo@example.com", self.emails_da_listagem(response))
        self.assertNotIn("inativo@example.com", self.emails_da_listagem(response))

    def test_filtro_somente_inativos(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("ativo@example.com")
        self.criar_usuario("inativo@example.com", is_active=False)
        self.client.force_login(admin)

        response = self.client.get(
            reverse("usuarios:admin_usuarios_lista"),
            {"status": "inativo"},
        )

        self.assertIn("inativo@example.com", self.emails_da_listagem(response))
        self.assertNotIn("ativo@example.com", self.emails_da_listagem(response))

    def test_combina_busca_tipo_e_status(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_usuario("marcos.ativo@example.com", first_name="Marcos")
        self.criar_usuario("marcos.inativo@example.com", first_name="Marcos", is_active=False)
        self.criar_usuario("marcia.admin@example.com", first_name="Marcia", is_staff=True)
        self.client.force_login(admin)

        response = self.client.get(
            reverse("usuarios:admin_usuarios_lista"),
            {"q": "mar", "tipo": "estudante", "status": "ativo"},
        )

        emails = self.emails_da_listagem(response)
        self.assertIn("marcos.ativo@example.com", emails)
        self.assertNotIn("marcos.inativo@example.com", emails)
        self.assertNotIn("marcia.admin@example.com", emails)

    def test_paginacao_preserva_busca_e_filtros(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        for indice in range(12):
            self.criar_usuario(
                f"pedro{indice}@example.com",
                first_name="Pedro",
                is_staff=False,
            )
        self.client.force_login(admin)

        response = self.client.get(
            reverse("usuarios:admin_usuarios_lista"),
            {"q": "pedro", "tipo": "estudante", "status": "ativo"},
        )

        self.assertContains(response, "q=pedro&amp;tipo=estudante&amp;status=ativo&amp;page=2")

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

    def test_cadastro_impede_email_duplicado(self):
        self.criar_usuario("ana@example.com")

        form = CadastroEstudanteForm(data=self.dados_cadastro())

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_cadastro_impede_email_duplicado_com_maiusculas(self):
        self.criar_usuario("ana@example.com")

        form = CadastroEstudanteForm(
            data=self.dados_cadastro(email="ANA@EXAMPLE.COM")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

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

    def test_edicao_de_perfil_nao_altera_permissoes(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        self.client.post(
            reverse("usuarios:perfil"),
            {
                "first_name": "Maria",
                "last_name": "Souza",
                "etapa_escolar": PerfilEstudante.EtapaEscolar.CURSINHO,
                "is_staff": "on",
                "is_superuser": "on",
                "is_active": "",
            },
        )

        estudante.refresh_from_db()
        self.assertFalse(estudante.is_staff)
        self.assertFalse(estudante.is_superuser)
        self.assertTrue(estudante.is_active)

    def test_estudante_altera_propria_senha_com_senha_atual(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.post(
            reverse("usuarios:perfil"),
            {
                "first_name": estudante.first_name,
                "last_name": estudante.last_name,
                "etapa_escolar": PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
                "senha_atual": "SenhaForte123",
                "nova_senha1": "NovaSenhaForte456",
                "nova_senha2": "NovaSenhaForte456",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("usuarios:perfil"))
        estudante.refresh_from_db()
        self.assertTrue(estudante.check_password("NovaSenhaForte456"))
        self.assertFalse(estudante.check_password("SenhaForte123"))

    def test_troca_de_senha_preserva_sessao_atual(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.post(
            reverse("usuarios:perfil"),
            {
                "first_name": estudante.first_name,
                "last_name": estudante.last_name,
                "etapa_escolar": PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
                "senha_atual": "SenhaForte123",
                "nova_senha1": "NovaSenhaForte456",
                "nova_senha2": "NovaSenhaForte456",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)

    def test_troca_de_senha_exige_senha_atual(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.post(
            reverse("usuarios:perfil"),
            {
                "first_name": estudante.first_name,
                "last_name": estudante.last_name,
                "etapa_escolar": PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
                "nova_senha1": "NovaSenhaForte456",
                "nova_senha2": "NovaSenhaForte456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe sua senha atual.")
        estudante.refresh_from_db()
        self.assertTrue(estudante.check_password("SenhaForte123"))

    def test_troca_de_senha_bloqueia_senha_atual_incorreta(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.post(
            reverse("usuarios:perfil"),
            {
                "first_name": estudante.first_name,
                "last_name": estudante.last_name,
                "etapa_escolar": PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
                "senha_atual": "SenhaErrada123",
                "nova_senha1": "NovaSenhaForte456",
                "nova_senha2": "NovaSenhaForte456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Senha atual incorreta.")
        estudante.refresh_from_db()
        self.assertTrue(estudante.check_password("SenhaForte123"))

    def test_troca_de_senha_exige_confirmacao_igual(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.post(
            reverse("usuarios:perfil"),
            {
                "first_name": estudante.first_name,
                "last_name": estudante.last_name,
                "etapa_escolar": PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
                "senha_atual": "SenhaForte123",
                "nova_senha1": "NovaSenhaForte456",
                "nova_senha2": "OutraSenhaForte456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "As senhas não coincidem.")
        estudante.refresh_from_db()
        self.assertTrue(estudante.check_password("SenhaForte123"))

    def test_troca_de_senha_pelo_perfil_nao_altera_permissoes(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        self.client.post(
            reverse("usuarios:perfil"),
            {
                "first_name": estudante.first_name,
                "last_name": estudante.last_name,
                "etapa_escolar": PerfilEstudante.EtapaEscolar.TERCEIRO_ANO,
                "senha_atual": "SenhaForte123",
                "nova_senha1": "NovaSenhaForte456",
                "nova_senha2": "NovaSenhaForte456",
                "is_staff": "on",
                "is_superuser": "on",
            },
        )

        estudante.refresh_from_db()
        self.assertFalse(estudante.is_staff)
        self.assertFalse(estudante.is_superuser)
        self.assertTrue(estudante.is_active)

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

    def test_administrador_nao_desativa_propria_conta(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("usuarios:admin_usuario_ativar", kwargs={"pk": admin.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        admin.refresh_from_db()
        self.assertTrue(admin.is_active)

    def test_staff_nao_exclui_superusuario(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        superusuario = self.User.objects.create_superuser(
            email="super@example.com",
            password="SenhaForte123",
            first_name="Super",
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("usuarios:admin_usuario_excluir", kwargs={"pk": superusuario.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.User.objects.filter(pk=superusuario.pk).exists())

    def test_staff_nao_desativa_superusuario(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        superusuario = self.User.objects.create_superuser(
            email="super@example.com",
            password="SenhaForte123",
            first_name="Super",
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("usuarios:admin_usuario_ativar", kwargs={"pk": superusuario.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        superusuario.refresh_from_db()
        self.assertTrue(superusuario.is_active)

    def test_administrador_nao_remove_proprio_is_staff(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.client.force_login(admin)

        self.client.post(
            reverse("usuarios:admin_usuario_editar", kwargs={"pk": admin.pk}),
            self.dados_admin_usuario(admin, is_staff=""),
        )

        admin.refresh_from_db()
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_active)

    def test_staff_comum_nao_transforma_usuario_em_superusuario_pela_interface(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(admin)

        self.client.post(
            reverse("usuarios:admin_usuario_editar", kwargs={"pk": estudante.pk}),
            self.dados_admin_usuario(estudante, is_superuser="on"),
        )

        estudante.refresh_from_db()
        self.assertFalse(estudante.is_superuser)

    def test_staff_nao_edita_atributos_criticos_de_superusuario(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        superusuario = self.User.objects.create_superuser(
            email="super@example.com",
            password="SenhaForte123",
            first_name="Super",
        )
        self.client.force_login(admin)

        self.client.post(
            reverse("usuarios:admin_usuario_editar", kwargs={"pk": superusuario.pk}),
            self.dados_admin_usuario(
                superusuario,
                email="alterado@example.com",
                is_active="",
                is_staff="",
                first_name="Nome alterado",
            ),
        )

        superusuario.refresh_from_db()
        self.assertEqual(superusuario.email, "super@example.com")
        self.assertTrue(superusuario.is_active)
        self.assertTrue(superusuario.is_staff)
        self.assertTrue(superusuario.is_superuser)
        self.assertEqual(superusuario.first_name, "Nome alterado")

    def test_criacao_administrativa_salva_senha_com_hash(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.client.force_login(admin)

        self.client.post(
            reverse("usuarios:admin_usuario_criar"),
            self.dados_admin_usuario(
                None,
                email="novo@example.com",
                password1="SenhaForte123",
                password2="SenhaForte123",
            ),
        )

        usuario = self.User.objects.get(email="novo@example.com")
        self.assertNotEqual(usuario.password, "SenhaForte123")
        self.assertTrue(usuario.check_password("SenhaForte123"))

    def test_edicao_sem_nova_senha_mantem_senha_anterior(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        estudante = self.criar_usuario("estudante@example.com")
        senha_anterior = estudante.password
        self.client.force_login(admin)

        self.client.post(
            reverse("usuarios:admin_usuario_editar", kwargs={"pk": estudante.pk}),
            self.dados_admin_usuario(estudante, first_name="Novo Nome"),
        )

        estudante.refresh_from_db()
        self.assertEqual(estudante.password, senha_anterior)
        self.assertTrue(estudante.check_password("SenhaForte123"))

    def test_edicao_com_nova_senha_usa_set_password(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(admin)

        self.client.post(
            reverse("usuarios:admin_usuario_editar", kwargs={"pk": estudante.pk}),
            self.dados_admin_usuario(
                estudante,
                password1="NovaSenhaForte456",
                password2="NovaSenhaForte456",
            ),
        )

        estudante.refresh_from_db()
        self.assertNotEqual(estudante.password, "NovaSenhaForte456")
        self.assertTrue(estudante.check_password("NovaSenhaForte456"))
        self.assertFalse(estudante.check_password("SenhaForte123"))

    def test_nova_senha_funciona_no_login(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(admin)
        self.client.post(
            reverse("usuarios:admin_usuario_editar", kwargs={"pk": estudante.pk}),
            self.dados_admin_usuario(
                estudante,
                password1="NovaSenhaForte456",
                password2="NovaSenhaForte456",
            ),
        )
        self.client.logout()

        response = self.client.post(
            reverse("usuarios:login"),
            {"username": "estudante@example.com", "password": "NovaSenhaForte456"},
            follow=True,
        )

        self.assertRedirects(response, reverse("usuarios:painel_estudante"))

    def test_senha_antiga_nao_funciona_apos_alteracao(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(admin)
        self.client.post(
            reverse("usuarios:admin_usuario_editar", kwargs={"pk": estudante.pk}),
            self.dados_admin_usuario(
                estudante,
                password1="NovaSenhaForte456",
                password2="NovaSenhaForte456",
            ),
        )
        self.client.logout()

        response = self.client.post(
            reverse("usuarios:login"),
            {"username": "estudante@example.com", "password": "SenhaForte123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
