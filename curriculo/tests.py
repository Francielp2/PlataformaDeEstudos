import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from usuarios.models import PerfilEstudante

from .forms import ConteudoForm, MateriaForm
from .models import Conteudo, Materia


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

    def criar_conteudo(self, titulo, materia=None, **extra):
        materia = materia or Materia.objects.get(slug="matematica")
        dados = {
            "materia": materia,
            "resumo": "Resumo do conteúdo.",
            "texto_estudo": "Material de estudo.",
            "dificuldade": Conteudo.DificuldadeConteudo.BASICO,
            "ordem_sugerida": 1,
            "status": Conteudo.StatusConteudo.RASCUNHO,
        }
        dados.update(extra)
        conteudo = Conteudo(titulo=titulo, **dados)
        conteudo.full_clean()
        conteudo.save()
        return conteudo

    def dados_conteudo(self, materia=None, **extra):
        materia = materia or Materia.objects.get(slug="matematica")
        dados = {
            "materia": str(materia.pk),
            "pai": "",
            "titulo": "Funções",
            "resumo": "Estudo introdutório de funções.",
            "texto_estudo": "Material textual de funções.",
            "dificuldade": Conteudo.DificuldadeConteudo.BASICO,
            "ordem_sugerida": "1",
            "status": Conteudo.StatusConteudo.RASCUNHO,
        }
        dados.update(extra)
        return dados

    def nomes_da_listagem_admin(self, response):
        return {materia.nome for materia in response.context["page_obj"]}

    def titulos_da_listagem_admin_conteudos(self, response):
        return {conteudo.titulo for conteudo in response.context["page_obj"]}

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

    def test_conteudo_model_criacao_valida(self):
        conteudo = self.criar_conteudo("Funções")

        self.assertEqual(conteudo.titulo, "Funções")
        self.assertEqual(conteudo.materia.slug, "matematica")

    def test_conteudo_model_usa_uuid(self):
        conteudo = self.criar_conteudo("Porcentagem")

        self.assertIsInstance(conteudo.id, uuid.UUID)

    def test_conteudo_gera_slug_automatico(self):
        conteudo = self.criar_conteudo("Função do 1º grau")

        self.assertEqual(conteudo.slug, "funcao-do-1o-grau")

    def test_mesmo_slug_permitido_em_materias_diferentes(self):
        matematica = Materia.objects.get(slug="matematica")
        fisica = Materia.objects.get(slug="fisica")
        conteudo_math = self.criar_conteudo("Introdução", materia=matematica)
        conteudo_fisica = self.criar_conteudo("Introdução", materia=fisica)

        self.assertEqual(conteudo_math.slug, "introducao")
        self.assertEqual(conteudo_fisica.slug, "introducao")

    def test_slug_repetido_na_mesma_materia_recebe_sufixo(self):
        materia = Materia.objects.get(slug="matematica")
        self.criar_conteudo("Funções", materia=materia)
        conteudo = self.criar_conteudo("Funções", materia=materia)

        self.assertEqual(conteudo.slug, "funcoes-2")

    def test_mesmo_slug_manual_proibido_na_mesma_materia(self):
        materia = Materia.objects.get(slug="matematica")
        self.criar_conteudo("Funções", materia=materia)
        conteudo = Conteudo(
            materia=materia,
            titulo="Outro título",
            slug="funcoes",
            resumo="Resumo.",
        )

        with self.assertRaises(ValidationError):
            conteudo.full_clean()

    def test_conteudo_titulo_vazio_invalido(self):
        conteudo = Conteudo(
            materia=Materia.objects.get(slug="matematica"),
            titulo="   ",
            resumo="Resumo.",
        )

        with self.assertRaises(ValidationError):
            conteudo.full_clean()

    def test_conteudo_normaliza_titulo(self):
        conteudo = self.criar_conteudo("  Funções    Afins  ")

        self.assertEqual(conteudo.titulo, "Funções Afins")

    def test_conteudo_pai_valido(self):
        pai = self.criar_conteudo("Funções")
        filho = self.criar_conteudo("Função do 1º grau", pai=pai)

        self.assertEqual(filho.pai, pai)

    def test_conteudo_pai_de_materia_diferente_invalido(self):
        pai = self.criar_conteudo("Cinemática", materia=Materia.objects.get(slug="fisica"))
        filho = Conteudo(
            materia=Materia.objects.get(slug="matematica"),
            pai=pai,
            titulo="Função do 1º grau",
            resumo="Resumo.",
        )

        with self.assertRaises(ValidationError):
            filho.full_clean()

    def test_conteudo_nao_pode_ser_pai_de_si_mesmo(self):
        conteudo = self.criar_conteudo("Funções")
        conteudo.pai = conteudo

        with self.assertRaises(ValidationError):
            conteudo.full_clean()

    def test_conteudo_detecta_ciclo(self):
        a = self.criar_conteudo("A")
        b = self.criar_conteudo("B", pai=a)
        c = self.criar_conteudo("C", pai=b)
        a.pai = c

        with self.assertRaises(ValidationError):
            a.full_clean()

    def test_mudanca_de_materia_com_filhos_inconsistentes_e_invalida(self):
        matematica = Materia.objects.get(slug="matematica")
        fisica = Materia.objects.get(slug="fisica")
        pai = self.criar_conteudo("Funções", materia=matematica)
        self.criar_conteudo("Função do 1º grau", materia=matematica, pai=pai)
        pai.materia = fisica

        with self.assertRaises(ValidationError):
            pai.full_clean()

    def test_conteudo_str(self):
        conteudo = self.criar_conteudo("Funções")

        self.assertEqual(str(conteudo), "Matemática - Funções")

    def test_conteudo_status_padrao(self):
        conteudo = Conteudo(
            materia=Materia.objects.get(slug="matematica"),
            titulo="Funções",
            resumo="Resumo.",
        )

        self.assertEqual(conteudo.status, Conteudo.StatusConteudo.RASCUNHO)

    def test_conteudo_dificuldade_padrao(self):
        conteudo = Conteudo(
            materia=Materia.objects.get(slug="matematica"),
            titulo="Funções",
            resumo="Resumo.",
        )

        self.assertEqual(conteudo.dificuldade, Conteudo.DificuldadeConteudo.BASICO)

    def test_conteudo_form_nao_expoe_campos_internos(self):
        form = ConteudoForm()

        self.assertEqual(
            set(form.fields),
            {
                "materia",
                "pai",
                "titulo",
                "resumo",
                "texto_estudo",
                "dificuldade",
                "ordem_sugerida",
                "status",
            },
        )

    def test_visitante_nao_acessa_listagem_de_conteudos(self):
        response = self.client.get(reverse("curriculo:conteudos_lista"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("usuarios:login"), response["Location"])

    def test_estudante_acessa_listagem_de_conteudos(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.get(reverse("curriculo:conteudos_lista"))

        self.assertEqual(response.status_code, 200)

    def test_estudante_ve_conteudo_publicado(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.criar_conteudo("Funções", status=Conteudo.StatusConteudo.PUBLICADO)
        self.client.force_login(estudante)

        response = self.client.get(reverse("curriculo:conteudos_lista"))

        self.assertContains(response, "Funções")

    def test_estudante_nao_ve_rascunho_ou_arquivado(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.criar_conteudo("Rascunho", status=Conteudo.StatusConteudo.RASCUNHO)
        self.criar_conteudo("Arquivado", status=Conteudo.StatusConteudo.ARQUIVADO)
        self.client.force_login(estudante)

        response = self.client.get(reverse("curriculo:conteudos_lista"))

        self.assertNotContains(response, "Rascunho")
        self.assertNotContains(response, "Arquivado")

    def test_estudante_filtra_conteudos_por_materia(self):
        estudante = self.criar_usuario("estudante@example.com")
        matematica = Materia.objects.get(slug="matematica")
        fisica = Materia.objects.get(slug="fisica")
        self.criar_conteudo("Funções", materia=matematica, status=Conteudo.StatusConteudo.PUBLICADO)
        self.criar_conteudo("Cinemática", materia=fisica, status=Conteudo.StatusConteudo.PUBLICADO)
        self.client.force_login(estudante)

        response = self.client.get(
            reverse("curriculo:conteudos_lista"),
            {"materia": "matematica"},
        )

        self.assertContains(response, "Funções")
        self.assertNotContains(response, "Cinemática")

    def test_estudante_filtra_conteudos_por_dificuldade(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.criar_conteudo("Básico", status=Conteudo.StatusConteudo.PUBLICADO)
        self.criar_conteudo(
            "Avançado",
            dificuldade=Conteudo.DificuldadeConteudo.AVANCADO,
            status=Conteudo.StatusConteudo.PUBLICADO,
        )
        self.client.force_login(estudante)

        response = self.client.get(
            reverse("curriculo:conteudos_lista"),
            {"dificuldade": Conteudo.DificuldadeConteudo.AVANCADO},
        )

        titulos = {conteudo.titulo for conteudo in response.context["conteudos"]}
        self.assertIn("Avançado", titulos)
        self.assertNotIn("Básico", titulos)

    def test_detalhe_publicado_funciona_para_estudante(self):
        estudante = self.criar_usuario("estudante@example.com")
        conteudo = self.criar_conteudo("Funções", status=Conteudo.StatusConteudo.PUBLICADO)
        self.client.force_login(estudante)

        response = self.client.get(
            reverse(
                "curriculo:conteudo_detalhe",
                kwargs={"materia_slug": conteudo.materia.slug, "conteudo_slug": conteudo.slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Materiais de estudo")
        self.assertContains(
            response,
            "Materiais de estudo serão disponibilizados futuramente neste espaço.",
        )
        self.assertNotContains(response, "Material de estudo.")

    def test_detalhe_de_rascunho_e_arquivado_retorna_404(self):
        estudante = self.criar_usuario("estudante@example.com")
        rascunho = self.criar_conteudo("Rascunho", status=Conteudo.StatusConteudo.RASCUNHO)
        arquivado = self.criar_conteudo("Arquivado", status=Conteudo.StatusConteudo.ARQUIVADO)
        self.client.force_login(estudante)

        for conteudo in (rascunho, arquivado):
            response = self.client.get(
                reverse(
                    "curriculo:conteudo_detalhe",
                    kwargs={
                        "materia_slug": conteudo.materia.slug,
                        "conteudo_slug": conteudo.slug,
                    },
                )
            )
            self.assertEqual(response.status_code, 404)

    def test_conteudo_de_materia_inativa_nao_fica_acessivel(self):
        estudante = self.criar_usuario("estudante@example.com")
        materia = self.criar_materia("Geografia", ativa=False)
        conteudo = self.criar_conteudo(
            "Cartografia",
            materia=materia,
            status=Conteudo.StatusConteudo.PUBLICADO,
        )
        self.client.force_login(estudante)

        response = self.client.get(
            reverse(
                "curriculo:conteudo_detalhe",
                kwargs={"materia_slug": materia.slug, "conteudo_slug": conteudo.slug},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_slug_de_materia_incorreto_retorna_404(self):
        estudante = self.criar_usuario("estudante@example.com")
        conteudo = self.criar_conteudo("Funções", status=Conteudo.StatusConteudo.PUBLICADO)
        self.client.force_login(estudante)

        response = self.client.get(
            reverse(
                "curriculo:conteudo_detalhe",
                kwargs={"materia_slug": "fisica", "conteudo_slug": conteudo.slug},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_conteudo_nao_pertencente_a_materia_da_url_retorna_404(self):
        estudante = self.criar_usuario("estudante@example.com")
        fisica = Materia.objects.get(slug="fisica")
        conteudo = self.criar_conteudo(
            "Cinemática",
            materia=fisica,
            status=Conteudo.StatusConteudo.PUBLICADO,
        )
        self.client.force_login(estudante)

        response = self.client.get(
            reverse(
                "curriculo:conteudo_detalhe",
                kwargs={"materia_slug": "matematica", "conteudo_slug": conteudo.slug},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_subconteudos_publicados_aparecem(self):
        estudante = self.criar_usuario("estudante@example.com")
        pai = self.criar_conteudo("Funções", status=Conteudo.StatusConteudo.PUBLICADO)
        filho = self.criar_conteudo(
            "Função do 1º grau",
            pai=pai,
            status=Conteudo.StatusConteudo.PUBLICADO,
        )
        self.client.force_login(estudante)

        response = self.client.get(
            reverse(
                "curriculo:conteudo_detalhe",
                kwargs={"materia_slug": pai.materia.slug, "conteudo_slug": pai.slug},
            )
        )

        self.assertContains(response, filho.titulo)

    def test_subconteudos_nao_publicados_nao_aparecem(self):
        estudante = self.criar_usuario("estudante@example.com")
        pai = self.criar_conteudo("Funções", status=Conteudo.StatusConteudo.PUBLICADO)
        filho = self.criar_conteudo(
            "Função do 1º grau",
            pai=pai,
            status=Conteudo.StatusConteudo.RASCUNHO,
        )
        self.client.force_login(estudante)

        response = self.client.get(
            reverse(
                "curriculo:conteudo_detalhe",
                kwargs={"materia_slug": pai.materia.slug, "conteudo_slug": pai.slug},
            )
        )

        self.assertNotContains(response, filho.titulo)

    def test_materia_detalhe_integra_conteudos_publicados(self):
        estudante = self.criar_usuario("estudante@example.com")
        materia = Materia.objects.get(slug="matematica")
        self.criar_conteudo("Funções", materia=materia, status=Conteudo.StatusConteudo.PUBLICADO)
        self.criar_conteudo("Rascunho", materia=materia, status=Conteudo.StatusConteudo.RASCUNHO)
        self.client.force_login(estudante)

        response = self.client.get(
            reverse("curriculo:materia_detalhe", kwargs={"slug": materia.slug})
        )

        self.assertContains(response, "Funções")
        self.assertNotContains(response, "Rascunho")

    def test_estudante_nao_acessa_admin_conteudos(self):
        estudante = self.criar_usuario("estudante@example.com")
        self.client.force_login(estudante)

        response = self.client.get(reverse("curriculo_admin:admin_conteudos_lista"))

        self.assertEqual(response.status_code, 403)

    def test_staff_e_superuser_acessam_admin_conteudos(self):
        staff = self.criar_usuario("staff@example.com", is_staff=True)
        superuser = self.User.objects.create_superuser(
            email="super@example.com",
            password="SenhaForte123",
            first_name="Super",
        )

        self.client.force_login(staff)
        response_staff = self.client.get(reverse("curriculo_admin:admin_conteudos_lista"))
        self.client.force_login(superuser)
        response_super = self.client.get(reverse("curriculo_admin:admin_conteudos_lista"))

        self.assertEqual(response_staff.status_code, 200)
        self.assertEqual(response_super.status_code, 200)

    def test_staff_cria_conteudo_com_criado_por(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        materia = Materia.objects.get(slug="matematica")
        self.client.force_login(admin)

        response = self.client.post(
            reverse("curriculo_admin:admin_conteudo_criar"),
            self.dados_conteudo(materia=materia),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        conteudo = Conteudo.objects.get(titulo="Funções")
        self.assertEqual(conteudo.criado_por, admin)

    def test_edicao_conteudo_preserva_criado_por_e_slug(self):
        criador = self.criar_usuario("criador@example.com", is_staff=True)
        editor = self.criar_usuario("editor@example.com", is_staff=True)
        conteudo = self.criar_conteudo("Funções", criado_por=criador)
        slug_original = conteudo.slug
        self.client.force_login(editor)

        self.client.post(
            reverse("curriculo_admin:admin_conteudo_editar", kwargs={"pk": conteudo.pk}),
            self.dados_conteudo(
                materia=conteudo.materia,
                titulo="Funções Editadas",
                status=Conteudo.StatusConteudo.PUBLICADO,
            ),
        )

        conteudo.refresh_from_db()
        self.assertEqual(conteudo.criado_por, criador)
        self.assertEqual(conteudo.slug, slug_original)
        self.assertEqual(conteudo.titulo, "Funções Editadas")

    def test_admin_busca_parcial_conteudo(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_conteudo("Funções")
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_conteudos_lista"),
            {"q": "func"},
        )

        self.assertIn("Funções", self.titulos_da_listagem_admin_conteudos(response))

    def test_admin_busca_por_nome_da_materia(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        self.criar_conteudo("Funções", materia=Materia.objects.get(slug="matematica"))
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_conteudos_lista"),
            {"q": "mat"},
        )

        self.assertIn("Funções", self.titulos_da_listagem_admin_conteudos(response))

    def test_admin_filtra_por_materia_status_e_dificuldade(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        matematica = Materia.objects.get(slug="matematica")
        fisica = Materia.objects.get(slug="fisica")
        self.criar_conteudo(
            "Funções",
            materia=matematica,
            dificuldade=Conteudo.DificuldadeConteudo.BASICO,
            status=Conteudo.StatusConteudo.PUBLICADO,
        )
        self.criar_conteudo(
            "Cinemática",
            materia=fisica,
            dificuldade=Conteudo.DificuldadeConteudo.AVANCADO,
            status=Conteudo.StatusConteudo.PUBLICADO,
        )
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_conteudos_lista"),
            {
                "materia": "matematica",
                "status": Conteudo.StatusConteudo.PUBLICADO,
                "dificuldade": Conteudo.DificuldadeConteudo.BASICO,
            },
        )

        titulos = self.titulos_da_listagem_admin_conteudos(response)
        self.assertIn("Funções", titulos)
        self.assertNotIn("Cinemática", titulos)

    def test_admin_paginacao_preserva_parametros(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        for indice in range(12):
            self.criar_conteudo(
                f"Função {indice}",
                status=Conteudo.StatusConteudo.PUBLICADO,
            )
        self.client.force_login(admin)

        response = self.client.get(
            reverse("curriculo_admin:admin_conteudos_lista"),
            {
                "q": "Função",
                "materia": "matematica",
                "status": Conteudo.StatusConteudo.PUBLICADO,
                "dificuldade": Conteudo.DificuldadeConteudo.BASICO,
            },
        )

        self.assertContains(
            response,
            "q=Fun%C3%A7%C3%A3o&amp;materia=matematica&amp;status=published&amp;dificuldade=basic&amp;page=2",
        )

    def test_get_nao_altera_status_de_conteudo(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        conteudo = self.criar_conteudo("Funções", status=Conteudo.StatusConteudo.RASCUNHO)
        self.client.force_login(admin)

        response = self.client.get(
            reverse(
                "curriculo_admin:admin_conteudo_alterar_status",
                kwargs={"pk": conteudo.pk, "status": Conteudo.StatusConteudo.PUBLICADO},
            )
        )

        self.assertEqual(response.status_code, 405)
        conteudo.refresh_from_db()
        self.assertEqual(conteudo.status, Conteudo.StatusConteudo.RASCUNHO)

    def test_post_altera_status_de_conteudo(self):
        admin = self.criar_usuario("admin@example.com", is_staff=True)
        conteudo = self.criar_conteudo("Funções", status=Conteudo.StatusConteudo.RASCUNHO)
        self.client.force_login(admin)

        response = self.client.post(
            reverse(
                "curriculo_admin:admin_conteudo_alterar_status",
                kwargs={"pk": conteudo.pk, "status": Conteudo.StatusConteudo.PUBLICADO},
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        conteudo.refresh_from_db()
        self.assertEqual(conteudo.status, Conteudo.StatusConteudo.PUBLICADO)

    def test_estudante_nao_envia_post_de_status_de_conteudo(self):
        estudante = self.criar_usuario("estudante@example.com")
        conteudo = self.criar_conteudo("Funções", status=Conteudo.StatusConteudo.RASCUNHO)
        self.client.force_login(estudante)

        response = self.client.post(
            reverse(
                "curriculo_admin:admin_conteudo_alterar_status",
                kwargs={"pk": conteudo.pk, "status": Conteudo.StatusConteudo.PUBLICADO},
            )
        )

        self.assertEqual(response.status_code, 403)
        conteudo.refresh_from_db()
        self.assertEqual(conteudo.status, Conteudo.StatusConteudo.RASCUNHO)
