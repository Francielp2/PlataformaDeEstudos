import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from usuarios.models import PerfilEstudante

from .forms import MateriaForm
from .models import Materia


class CurriculoMateriaTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def criar_usuario(self, email, password="SenhaForte123", **extra):
        usuario = self.User.objects.create_user(
            email=email,
            password=password,
            first_name=extra.pop("first_name", "Usuário"),
            **extra,
        )
        PerfilEstudante.objects.create(usuario=usuario)
        return usuario

    def criar_materia(self, nome, **extra):
        dados = {
            "descricao": "Descrição da matéria.",
            "ordem_exibicao": 10,
            "ativa": True,
        }
        dados.update(extra)
        materia = Materia(nome=nome, **dados)
        materia.full_clean()
        materia.save()
        return materia

    def dados_materia(self, **extra):
        dados = {
            "nome": "Geografia",
            "descricao": "Descrição de Geografia.",
            "ordem_exibicao": "4",
            "ativa": "on",
        }
        dados.update(extra)
        return dados

    def nomes_da_listagem_admin(self, response):
        return {materia.nome for materia in response.context["page_obj"]}

    def test_model_criacao_valida(self):
        materia = self.criar_materia("Geografia")

        self.assertEqual(materia.nome, "Geografia")
        self.assertTrue(materia.ativa)

    def test_model_usa_uuid(self):
        materia = self.criar_materia("História")

        self.assertIsInstance(materia.id, uuid.UUID)

    def test_model_gera_slug_automatico(self):
        materia = self.criar_materia("Língua Portuguesa")

        self.assertEqual(materia.slug, "lingua-portuguesa")

    def test_model_str_retorna_nome(self):
        materia = self.criar_materia("Redação")

        self.assertEqual(str(materia), "Redação")

    def test_model_ordenacao_padrao(self):
        Materia.objects.all().delete()
        self.criar_materia("Química", ordem_exibicao=2)
        self.criar_materia("Física", ordem_exibicao=1)
        self.criar_materia("Biologia", ordem_exibicao=1)

        nomes = list(Materia.objects.values_list("nome", flat=True))

        self.assertEqual(nomes, ["Biologia", "Física", "Química"])

    def test_model_bloqueia_nome_duplicado(self):
        self.criar_materia("Geografia")
        materia = Materia(nome="Geografia")

        with self.assertRaises(ValidationError):
            materia.full_clean()

    def test_model_bloqueia_nome_duplicado_com_diferenca_de_caixa(self):
        self.criar_materia("Sociologia")
        materia = Materia(nome="SOCIOLOGIA")

        with self.assertRaises(ValidationError):
            materia.full_clean()

    def test_model_remove_espacos_extras_do_nome(self):
        materia = self.criar_materia("  Artes   Visuais  ")

        self.assertEqual(materia.nome, "Artes Visuais")
        self.assertEqual(materia.slug, "artes-visuais")

    def test_slug_conflitante_recebe_sufixo(self):
        self.criar_materia("Projeto Integrador")
        materia = self.criar_materia("Projeto-Integrador")

        self.assertEqual(materia.slug, "projeto-integrador-2")

    def test_form_nao_expoe_campos_internos(self):
        form = MateriaForm()

        self.assertEqual(
            set(form.fields),
            {"nome", "descricao", "ordem_exibicao", "ativa"},
        )

    def test_data_migration_cria_materias_iniciais(self):
        self.assertTrue(Materia.objects.filter(slug="matematica").exists())
        self.assertTrue(Materia.objects.filter(slug="fisica").exists())
        self.assertTrue(Materia.objects.filter(slug="quimica").exists())
        self.assertIsNone(Materia.objects.get(slug="matematica").criado_por)

    def test_visitante_nao_acessa_listagem_de_materias(self):
        response = self.client.get(reverse("curriculo:materias_lista"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("usuarios:login"), response["Location"])

    def test_estudante_autenticado_acessa_materias(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.get(reverse("curriculo:materias_lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matemática")

    def test_estudante_ve_somente_materias_ativas(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.criar_materia("Ativa", ativa=True)
        self.criar_materia("Inativa", ativa=False)
        self.client.force_login(estudante)

        response = self.client.get(reverse("curriculo:materias_lista"))

        self.assertContains(response, "Ativa")
        self.assertNotContains(response, "Inativa")

    def test_detalhe_de_materia_ativa_para_estudante(self):
        estudante = self.criar_usuario("estudante@example.com")
        materia = self.criar_materia("Geografia", descricao="Mapas e território.")
        self.client.force_login(estudante)

        response = self.client.get(
            reverse("curriculo:materia_detalhe", kwargs={"slug": materia.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mapas e território.")

    def test_acesso_direto_a_materia_inativa_retorna_404(self):
        estudante = self.criar_usuario("estudante@example.com")
        materia = self.criar_materia("Geografia", ativa=False)
        self.client.force_login(estudante)

        response = self.client.get(
            reverse("curriculo:materia_detalhe", kwargs={"slug": materia.slug})
        )

        self.assertEqual(response.status_code, 404)

    def test_estudante_nao_acessa_administracao_de_materias(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.get(reverse("curriculo_admin:admin_materias_lista"))

        self.assertEqual(response.status_code, 403)

    def test_staff_acessa_listagem_administrativa(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.client.force_login(admin)

        response = self.client.get(reverse("curriculo_admin:admin_materias_lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gerenciar matérias")

    def test_superuser_acessa_listagem_administrativa(self):
        admin = self.User.objects.create_superuser(
            email="super@example.com",
            password="SenhaForte123",
            first_name="Super",
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("curriculo_admin:admin_materias_lista"))

        self.assertEqual(response.status_code, 200)

    def test_staff_cria_materia_com_criado_por_automatico(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("curriculo_admin:admin_materia_criar"),
            self.dados_materia(nome="Geografia"),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        materia = Materia.objects.get(nome="Geografia")
        self.assertEqual(materia.criado_por, admin)
        self.assertEqual(materia.slug, "geografia")

    def test_staff_edita_materia(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        materia = self.criar_materia("Geografia", criado_por=admin)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("curriculo_admin:admin_materia_editar", kwargs={"slug": materia.slug}),
            self.dados_materia(
                nome="Geografia Atualizada",
                descricao="Nova descrição.",
                ordem_exibicao="8",
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        materia.refresh_from_db()
        self.assertEqual(materia.nome, "Geografia Atualizada")
        self.assertEqual(materia.descricao, "Nova descrição.")
        self.assertEqual(materia.ordem_exibicao, 8)

    def test_edicao_nao_altera_criado_por(self):
        criador = self.criar_usuario("criador@example.com", is_staff=True)
        editor = self.criar_usuario("editor@example.com", is_staff=True)
        materia = self.criar_materia("Geografia", criado_por=criador)
        self.client.force_login(editor)

        self.client.post(
            reverse("curriculo_admin:admin_materia_editar", kwargs={"slug": materia.slug}),
            self.dados_materia(nome="Geografia Editada"),
        )

        materia.refresh_from_db()
        self.assertEqual(materia.criado_por, criador)

    def test_edicao_de_nome_preserva_slug(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        materia = self.criar_materia("Geografia", criado_por=admin)
        slug_original = materia.slug
        self.client.force_login(admin)

        self.client.post(
            reverse("curriculo_admin:admin_materia_editar", kwargs={"slug": materia.slug}),
            self.dados_materia(nome="Geografia Editada"),
        )

        materia.refresh_from_db()
        self.assertEqual(materia.slug, slug_original)

    def test_desativacao_funciona_via_post(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        materia = self.criar_materia("Geografia")
        self.client.force_login(admin)

        response = self.client.post(
            reverse(
                "curriculo_admin:admin_materia_alternar_status",
                kwargs={"slug": materia.slug},
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        materia.refresh_from_db()
        self.assertFalse(materia.ativa)

    def test_ativacao_funciona_via_post(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        materia = self.criar_materia("Geografia", ativa=False)
        self.client.force_login(admin)

        self.client.post(
            reverse(
                "curriculo_admin:admin_materia_alternar_status",
                kwargs={"slug": materia.slug},
            )
        )

        materia.refresh_from_db()
        self.assertTrue(materia.ativa)

    def test_get_nao_altera_status(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        materia = self.criar_materia("Geografia", ativa=True)
        self.client.force_login(admin)

        response = self.client.get(
            reverse(
                "curriculo_admin:admin_materia_alternar_status",
                kwargs={"slug": materia.slug},
            )
        )

        self.assertEqual(response.status_code, 405)
        materia.refresh_from_db()
        self.assertTrue(materia.ativa)

    def test_busca_administrativa_por_nome(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_materia("Geografia")
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_materias_lista"),
            {"q": "geo"},
        )

        self.assertIn("Geografia", self.nomes_da_listagem_admin(response))
        self.assertNotIn("Matemática", self.nomes_da_listagem_admin(response))

    def test_busca_administrativa_por_slug(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        materia = self.criar_materia("Língua Portuguesa")
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_materias_lista"),
            {"q": "lingua"},
        )

        self.assertIn(materia.nome, self.nomes_da_listagem_admin(response))

    def test_filtro_administrativo_ativas(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_materia("Ativa", ativa=True)
        self.criar_materia("Inativa", ativa=False)
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_materias_lista"),
            {"status": "ativas"},
        )

        self.assertIn("Ativa", self.nomes_da_listagem_admin(response))
        self.assertNotIn("Inativa", self.nomes_da_listagem_admin(response))

    def test_filtro_administrativo_inativas(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_materia("Ativa", ativa=True)
        self.criar_materia("Inativa", ativa=False)
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_materias_lista"),
            {"status": "inativas"},
        )

        self.assertIn("Inativa", self.nomes_da_listagem_admin(response))
        self.assertNotIn("Ativa", self.nomes_da_listagem_admin(response))

    def test_combina_busca_e_filtro_administrativo(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_materia("Geografia", ativa=True)
        self.criar_materia("Geometria", ativa=False)
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_materias_lista"),
            {"q": "geo", "status": "inativas"},
        )

        self.assertIn("Geometria", self.nomes_da_listagem_admin(response))
        self.assertNotIn("Geografia", self.nomes_da_listagem_admin(response))

    def test_paginacao_preserva_busca_e_filtro(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        for indice in range(12):
            self.criar_materia(f"Materia Extra {indice}", ativa=True)
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_materias_lista"),
            {"q": "Materia Extra", "status": "ativas"},
        )

        self.assertContains(
            response,
            "q=Materia+Extra&amp;status=ativas&amp;page=2",
        )
