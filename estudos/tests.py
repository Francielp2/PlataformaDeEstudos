from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from curriculo.models import Conteudo, Materia
from questoes.models import Alternativa, Questao, QuestaoConteudo, RespostaQuestao

from .models import ConteudoEstudado, ItemMinhaLista


Usuario = get_user_model()


class EstudosTestMixin:
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email="aluno@example.com",
            password="SenhaForte123",
            first_name="Aluno",
        )
        self.outro_usuario = Usuario.objects.create_user(
            email="outro@example.com",
            password="SenhaForte123",
            first_name="Outro",
        )
        self.staff = Usuario.objects.create_user(
            email="admin@example.com",
            password="SenhaForte123",
            first_name="Admin",
            is_staff=True,
        )
        self.matematica = Materia.objects.get(nome="Matemática")
        self.fisica = Materia.objects.get(nome="Física")
        self.conteudo = Conteudo.objects.create(
            materia=self.matematica,
            titulo="Porcentagem",
            resumo="Resumo de porcentagem",
            status=Conteudo.StatusConteudo.PUBLICADO,
            criado_por=self.staff,
        )
        self.outro_conteudo = Conteudo.objects.create(
            materia=self.matematica,
            titulo="Funções",
            resumo="Resumo de funções",
            dificuldade=Conteudo.DificuldadeConteudo.INTERMEDIARIO,
            status=Conteudo.StatusConteudo.PUBLICADO,
            criado_por=self.staff,
        )
        self.questao = self.criar_questao("MAT-001", self.conteudo)

    def criar_questao(
        self,
        codigo,
        conteudo,
        status=Questao.StatusQuestao.PUBLICADA,
    ):
        questao = Questao.objects.create(
            codigo=codigo,
            materia=conteudo.materia,
            enunciado=f"Enunciado {codigo}",
            explicacao="Explicação",
            status=Questao.StatusQuestao.RASCUNHO,
            criado_por=self.staff,
        )
        Alternativa.objects.create(
            questao=questao,
            chave="A",
            texto="Correta",
            correta=True,
            ordem=1,
        )
        Alternativa.objects.create(
            questao=questao,
            chave="B",
            texto="Incorreta",
            correta=False,
            ordem=2,
        )
        QuestaoConteudo.objects.create(questao=questao, conteudo=conteudo, principal=True)
        if status == Questao.StatusQuestao.PUBLICADA:
            questao.publicar()
        else:
            questao.status = status
            questao.save(update_fields=["status", "atualizado_em"])
        return questao


class ItemMinhaListaModelTests(EstudosTestMixin, TestCase):
    def test_itens_validos_e_tipo(self):
        item_materia = ItemMinhaLista.objects.create(
            usuario=self.usuario,
            materia=self.matematica,
        )
        item_conteudo = ItemMinhaLista.objects.create(
            usuario=self.usuario,
            conteudo=self.conteudo,
        )
        item_questao = ItemMinhaLista.objects.create(
            usuario=self.usuario,
            questao=self.questao,
        )

        self.assertEqual(item_materia.tipo, "materia")
        self.assertEqual(item_materia.tipo_display, "Matéria")
        self.assertEqual(item_conteudo.tipo, "conteudo")
        self.assertEqual(item_questao.tipo, "questao")

    def test_exatamente_um_alvo(self):
        casos_invalidos = [
            ItemMinhaLista(usuario=self.usuario),
            ItemMinhaLista(
                usuario=self.usuario,
                materia=self.matematica,
                conteudo=self.conteudo,
            ),
            ItemMinhaLista(
                usuario=self.usuario,
                materia=self.matematica,
                conteudo=self.conteudo,
                questao=self.questao,
            ),
        ]

        for item in casos_invalidos:
            with self.assertRaises(ValidationError):
                item.full_clean()

    def test_nao_duplica_mesmo_alvo_para_mesmo_usuario(self):
        ItemMinhaLista.objects.create(usuario=self.usuario, materia=self.matematica)
        ItemMinhaLista.objects.create(usuario=self.usuario, conteudo=self.conteudo)
        ItemMinhaLista.objects.create(usuario=self.usuario, questao=self.questao)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ItemMinhaLista.objects.create(usuario=self.usuario, materia=self.matematica)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ItemMinhaLista.objects.create(usuario=self.usuario, conteudo=self.conteudo)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ItemMinhaLista.objects.create(usuario=self.usuario, questao=self.questao)

        ItemMinhaLista.objects.create(usuario=self.outro_usuario, materia=self.matematica)
        ItemMinhaLista.objects.create(usuario=self.outro_usuario, conteudo=self.conteudo)
        ItemMinhaLista.objects.create(usuario=self.outro_usuario, questao=self.questao)


class ConteudoEstudadoModelTests(EstudosTestMixin, TestCase):
    def test_marcacao_valida_unica_por_usuario(self):
        ConteudoEstudado.objects.create(usuario=self.usuario, conteudo=self.conteudo)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ConteudoEstudado.objects.create(
                    usuario=self.usuario,
                    conteudo=self.conteudo,
                )

        ConteudoEstudado.objects.create(
            usuario=self.outro_usuario,
            conteudo=self.conteudo,
        )

    def test_minha_lista_e_estudado_sao_independentes(self):
        ItemMinhaLista.objects.create(usuario=self.usuario, conteudo=self.conteudo)
        ConteudoEstudado.objects.create(usuario=self.usuario, conteudo=self.conteudo)

        ItemMinhaLista.objects.filter(usuario=self.usuario, conteudo=self.conteudo).delete()
        self.assertTrue(
            ConteudoEstudado.objects.filter(
                usuario=self.usuario,
                conteudo=self.conteudo,
            ).exists()
        )

        ItemMinhaLista.objects.create(usuario=self.usuario, conteudo=self.conteudo)
        ConteudoEstudado.objects.filter(usuario=self.usuario, conteudo=self.conteudo).delete()
        self.assertTrue(
            ItemMinhaLista.objects.filter(
                usuario=self.usuario,
                conteudo=self.conteudo,
            ).exists()
        )


class EstudosViewTests(EstudosTestMixin, TestCase):
    def test_estudante_adiciona_remove_materia_e_botao_muda(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("curriculo:materias_lista"))
        self.assertContains(response, "Adicionar à Minha Lista")

        self.client.post(
            reverse("estudos:alternar_materia_minha_lista", args=[self.matematica.pk])
        )
        self.assertTrue(
            ItemMinhaLista.objects.filter(
                usuario=self.usuario,
                materia=self.matematica,
            ).exists()
        )

        response = self.client.get(reverse("curriculo:materias_lista"))
        self.assertContains(response, "Remover da Minha Lista")

        self.client.post(
            reverse("estudos:alternar_materia_minha_lista", args=[self.matematica.pk])
        )
        self.assertFalse(
            ItemMinhaLista.objects.filter(
                usuario=self.usuario,
                materia=self.matematica,
            ).exists()
        )

    def test_nao_adiciona_materia_inativa(self):
        inativa = Materia.objects.create(nome="Biologia", ativa=False)
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("estudos:alternar_materia_minha_lista", args=[inativa.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            ItemMinhaLista.objects.filter(usuario=self.usuario, materia=inativa).exists()
        )

    def test_conteudo_lista_e_estudado_sao_independentes(self):
        self.client.force_login(self.usuario)

        self.client.post(
            reverse("estudos:alternar_conteudo_minha_lista", args=[self.conteudo.pk])
        )
        self.client.post(
            reverse("estudos:alternar_conteudo_estudado", args=[self.conteudo.pk])
        )
        self.assertTrue(
            ItemMinhaLista.objects.filter(
                usuario=self.usuario,
                conteudo=self.conteudo,
            ).exists()
        )
        self.assertTrue(
            ConteudoEstudado.objects.filter(
                usuario=self.usuario,
                conteudo=self.conteudo,
            ).exists()
        )

        self.client.post(
            reverse("estudos:alternar_conteudo_minha_lista", args=[self.conteudo.pk])
        )
        self.assertFalse(
            ItemMinhaLista.objects.filter(
                usuario=self.usuario,
                conteudo=self.conteudo,
            ).exists()
        )
        self.assertTrue(
            ConteudoEstudado.objects.filter(
                usuario=self.usuario,
                conteudo=self.conteudo,
            ).exists()
        )

        self.client.post(
            reverse("estudos:alternar_conteudo_estudado", args=[self.conteudo.pk])
        )
        self.assertFalse(
            ConteudoEstudado.objects.filter(
                usuario=self.usuario,
                conteudo=self.conteudo,
            ).exists()
        )

    def test_marcar_estudado_nao_adiciona_minha_lista(self):
        self.client.force_login(self.usuario)
        self.client.post(
            reverse("estudos:alternar_conteudo_estudado", args=[self.conteudo.pk])
        )

        self.assertFalse(
            ItemMinhaLista.objects.filter(
                usuario=self.usuario,
                conteudo=self.conteudo,
            ).exists()
        )

    def test_conteudo_indisponivel_nao_pode_ser_adicionado(self):
        rascunho = Conteudo.objects.create(
            materia=self.matematica,
            titulo="Rascunho",
            resumo="Resumo",
            status=Conteudo.StatusConteudo.RASCUNHO,
        )
        arquivado = Conteudo.objects.create(
            materia=self.matematica,
            titulo="Arquivado",
            resumo="Resumo",
            status=Conteudo.StatusConteudo.ARQUIVADO,
        )
        self.client.force_login(self.usuario)

        for conteudo in [rascunho, arquivado]:
            response = self.client.post(
                reverse("estudos:alternar_conteudo_minha_lista", args=[conteudo.pk])
            )
            self.assertEqual(response.status_code, 404)

    def test_questao_adiciona_remove_sem_alterar_respostas(self):
        alternativa = self.questao.alternativas.get(correta=True)
        RespostaQuestao.objects.create(
            usuario=self.usuario,
            questao=self.questao,
            alternativa_escolhida=alternativa,
            correta=False,
        )
        self.client.force_login(self.usuario)

        self.client.post(
            reverse("estudos:alternar_questao_minha_lista", args=[self.questao.pk])
        )
        self.client.post(
            reverse("estudos:alternar_questao_minha_lista", args=[self.questao.pk])
        )

        self.assertEqual(
            RespostaQuestao.objects.filter(usuario=self.usuario, questao=self.questao).count(),
            1,
        )

    def test_questao_arquivada_nao_pode_ser_adicionada(self):
        arquivada = self.criar_questao(
            "MAT-002",
            self.conteudo,
            status=Questao.StatusQuestao.ARQUIVADA,
        )
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("estudos:alternar_questao_minha_lista", args=[arquivada.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_minha_lista_filtra_por_tipo_e_isola_usuario(self):
        ItemMinhaLista.objects.create(usuario=self.usuario, materia=self.matematica)
        ItemMinhaLista.objects.create(usuario=self.usuario, conteudo=self.conteudo)
        ItemMinhaLista.objects.create(usuario=self.usuario, questao=self.questao)
        ItemMinhaLista.objects.create(usuario=self.outro_usuario, materia=self.fisica)
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("estudos:minha_lista"))
        self.assertContains(response, "Matéria")
        self.assertContains(response, "Conteúdo")
        self.assertContains(response, "Questão")
        self.assertNotContains(response, "Física")

        response = self.client.get(reverse("estudos:minha_lista"), {"tipo": "materias"})
        self.assertContains(response, "Matemática")
        self.assertEqual([item.tipo for item in response.context["itens"]], ["materia"])

        response = self.client.get(reverse("estudos:minha_lista"), {"tipo": "conteudos"})
        self.assertContains(response, "Porcentagem")
        self.assertEqual([item.tipo for item in response.context["itens"]], ["conteudo"])

        response = self.client.get(reverse("estudos:minha_lista"), {"tipo": "questoes"})
        self.assertContains(response, "MAT-001")
        self.assertEqual([item.tipo for item in response.context["itens"]], ["questao"])

    def test_item_indisponivel_continua_listado_e_pode_ser_removido(self):
        item = ItemMinhaLista.objects.create(usuario=self.usuario, materia=self.matematica)
        self.matematica.ativa = False
        self.matematica.save(update_fields=["ativa", "atualizado_em"])
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("estudos:minha_lista"))
        self.assertContains(response, "Indisponível")

        self.client.post(reverse("estudos:remover_item_minha_lista", args=[item.pk]))
        self.assertFalse(ItemMinhaLista.objects.filter(pk=item.pk).exists())

    def test_estudados_filtra_e_mostra_estado_minha_lista(self):
        ConteudoEstudado.objects.create(usuario=self.usuario, conteudo=self.conteudo)
        ConteudoEstudado.objects.create(usuario=self.usuario, conteudo=self.outro_conteudo)
        ItemMinhaLista.objects.create(usuario=self.usuario, conteudo=self.conteudo)
        self.client.force_login(self.usuario)

        response = self.client.get(
            reverse("estudos:conteudos_estudados"),
            {
                "materia": self.matematica.slug,
                "dificuldade": Conteudo.DificuldadeConteudo.BASICO,
                "q": "porc",
            },
        )

        self.assertContains(response, "Porcentagem")
        self.assertContains(response, "Minha Lista")
        self.assertNotContains(response, "Funções")

    def test_seguranca_remover_item_de_outro_usuario_e_uuid_inexistente(self):
        item_outro = ItemMinhaLista.objects.create(
            usuario=self.outro_usuario,
            materia=self.matematica,
        )
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("estudos:remover_item_minha_lista", args=[item_outro.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ItemMinhaLista.objects.filter(pk=item_outro.pk).exists())

        response = self.client.post(
            reverse(
                "estudos:alternar_materia_minha_lista",
                args=["00000000-0000-0000-0000-000000000000"],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_post_de_outro_usuario_nao_remove_marcacao_estudado_de_terceiro(self):
        ConteudoEstudado.objects.create(
            usuario=self.outro_usuario,
            conteudo=self.conteudo,
        )
        self.client.force_login(self.usuario)

        self.client.post(
            reverse("estudos:alternar_conteudo_estudado", args=[self.conteudo.pk])
        )

        self.assertTrue(
            ConteudoEstudado.objects.filter(
                usuario=self.outro_usuario,
                conteudo=self.conteudo,
            ).exists()
        )
        self.assertTrue(
            ConteudoEstudado.objects.filter(
                usuario=self.usuario,
                conteudo=self.conteudo,
            ).exists()
        )

    def test_get_nao_altera_marcacoes(self):
        self.client.force_login(self.usuario)
        response = self.client.get(
            reverse("estudos:alternar_materia_minha_lista", args=[self.matematica.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.assertFalse(
            ItemMinhaLista.objects.filter(
                usuario=self.usuario,
                materia=self.matematica,
            ).exists()
        )
