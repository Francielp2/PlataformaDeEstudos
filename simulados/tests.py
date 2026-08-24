import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from curriculo.models import Conteudo, Materia
from estudos.models import ItemMinhaLista
from questoes.models import Alternativa, Questao, QuestaoConteudo

from .models import AlternativaSimulado, QuestaoSimulado, RespostaSimulado, Simulado, TentativaSimulado
from .services import criar_snapshot_de_questao, diagnostico_tentativa, importar_json


Usuario = get_user_model()


class SimuladoTestMixin:
    def setUp(self):
        self.estudante = Usuario.objects.create_user(
            email="aluno@example.com",
            password="SenhaForte123",
            first_name="Aluno",
        )
        self.outro_estudante = Usuario.objects.create_user(
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
            resumo="Resumo",
            status=Conteudo.StatusConteudo.PUBLICADO,
            criado_por=self.staff,
        )
        self.outro_conteudo = Conteudo.objects.create(
            materia=self.matematica,
            titulo="Função Afim",
            resumo="Resumo",
            status=Conteudo.StatusConteudo.PUBLICADO,
            criado_por=self.staff,
        )
        self.conteudo_fisica = Conteudo.objects.create(
            materia=self.fisica,
            titulo="Cinemática",
            resumo="Resumo",
            status=Conteudo.StatusConteudo.PUBLICADO,
            criado_por=self.staff,
        )

    def criar_questao(self, codigo="MAT-001", conteudos=None, materia=None):
        conteudos = list(conteudos or [self.conteudo])
        materia = materia or conteudos[0].materia
        questao = Questao.objects.create(
            codigo=codigo,
            materia=materia,
            enunciado=f"Enunciado {codigo}",
            explicacao="Explicação que pode revelar a resposta correta.",
            status=Questao.StatusQuestao.RASCUNHO,
            criado_por=self.staff,
        )
        Alternativa.objects.create(questao=questao, chave="A", texto="Correta original", correta=True, ordem=1)
        Alternativa.objects.create(questao=questao, chave="B", texto="Incorreta original", correta=False, ordem=2)
        for indice, conteudo in enumerate(conteudos):
            QuestaoConteudo.objects.create(questao=questao, conteudo=conteudo, principal=indice == 0)
        questao.publicar()
        return questao

    def criar_simulado(self, status=Simulado.StatusSimulado.RASCUNHO, tipo=Simulado.TipoSimulado.GERAL):
        simulado = Simulado.objects.create(
            titulo="Simulado Matemática",
            tipo=tipo,
            materia=self.matematica if tipo == Simulado.TipoSimulado.POR_MATERIA else None,
            status=Simulado.StatusSimulado.RASCUNHO,
            criado_por=self.staff,
        )
        if status == Simulado.StatusSimulado.PUBLICADO:
            criar_snapshot_de_questao(simulado, self.criar_questao())
            simulado.publicar()
        return simulado

    def primeira_alternativa(self, snapshot, correta=True):
        return snapshot.alternativas.get(correta=correta)

    def finalizar_com_resposta(self, simulado=None, correta=True):
        simulado = simulado or self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        tentativa = TentativaSimulado.objects.create(
            usuario=self.estudante,
            simulado=simulado,
            total_questoes=simulado.questoes.count(),
        )
        questao = simulado.questoes.first()
        RespostaSimulado.objects.create(
            tentativa=tentativa,
            questao_simulado=questao,
            alternativa_escolhida=self.primeira_alternativa(questao, correta=correta),
        )
        tentativa.finalizar()
        return tentativa


class SimuladoModelTests(SimuladoTestMixin, TestCase):
    def test_tipo_por_materia_exige_materia_e_geral_nao_aceita_materia(self):
        with self.assertRaises(ValidationError):
            Simulado(titulo="Por matéria", tipo=Simulado.TipoSimulado.POR_MATERIA).full_clean()
        with self.assertRaises(ValidationError):
            Simulado(titulo="Geral", tipo=Simulado.TipoSimulado.GERAL, materia=self.matematica).full_clean()

    def test_snapshot_nao_muda_quando_questao_original_e_editada_arquivada_ou_removida(self):
        questao = self.criar_questao()
        simulado = self.criar_simulado()
        snapshot = criar_snapshot_de_questao(simulado, questao)

        questao.enunciado = "Enunciado alterado"
        questao.explicacao = "Explicação alterada"
        questao.status = Questao.StatusQuestao.ARQUIVADA
        questao.save()
        questao.alternativas.filter(chave="A").update(texto="Correta alterada", correta=False)
        questao.alternativas.filter(chave="B").update(correta=True)
        questao.delete()

        snapshot.refresh_from_db()
        self.assertEqual(snapshot.enunciado, "Enunciado MAT-001")
        self.assertEqual(snapshot.explicacao, "Explicação que pode revelar a resposta correta.")
        self.assertIsNone(snapshot.questao_origem)
        self.assertEqual(snapshot.alternativas.get(chave="A").texto, "Correta original")
        self.assertTrue(snapshot.alternativas.get(chave="A").correta)

    def test_publicacao_exige_questoes_validas_e_conteudo_principal(self):
        simulado = self.criar_simulado()
        with self.assertRaises(ValidationError):
            simulado.publicar()

        questao = QuestaoSimulado.objects.create(simulado=simulado, enunciado="Q1", ordem=1)
        AlternativaSimulado.objects.create(questao_simulado=questao, chave="A", texto="A", correta=True, ordem=1)
        AlternativaSimulado.objects.create(questao_simulado=questao, chave="B", texto="B", correta=False, ordem=2)
        with self.assertRaises(ValidationError):
            simulado.publicar()

    def test_simulado_por_materia_rejeita_conteudo_de_outra_materia(self):
        simulado = self.criar_simulado(tipo=Simulado.TipoSimulado.POR_MATERIA)
        questao = self.criar_questao("FIS-001", conteudos=[self.conteudo_fisica], materia=self.fisica)
        with self.assertRaises(ValidationError):
            criar_snapshot_de_questao(simulado, questao)


class ImportacaoJsonTests(SimuladoTestMixin, TestCase):
    def payload(self, codigo="JSON-001", conteudos=None):
        conteudos = conteudos or [self.conteudo.slug]
        return {
            "questoes": [
                {
                    "codigo": codigo,
                    "enunciado": "Enunciado importado",
                    "explicacao": "Explicação importada",
                    "dificuldade": "medium",
                    "tipo_fonte": "enem",
                    "fonte_nome": "ENEM",
                    "fonte_ano": 2024,
                    "fonte_url": "https://example.com",
                    "conteudo_principal": conteudos[0],
                    "conteudos": conteudos,
                    "alternativas": [
                        {"chave": "A", "texto": "A", "correta": False, "ordem": 1},
                        {"chave": "B", "texto": "B", "correta": True, "ordem": 2},
                    ],
                }
            ]
        }

    def test_json_invalido_nao_cria_questao(self):
        simulado = self.criar_simulado()
        with self.assertRaises(ValidationError):
            importar_json(simulado, "{", self.staff)
        self.assertEqual(simulado.questoes.count(), 0)

    def test_conteudo_inexistente_cancela_importacao_inteira(self):
        simulado = self.criar_simulado()
        payload = self.payload(conteudos=["nao-existe"])
        with self.assertRaises(ValidationError):
            importar_json(simulado, json.dumps(payload), self.staff)
        self.assertEqual(simulado.questoes.count(), 0)

    def test_importacao_salva_snapshot_e_opcionalmente_banco_sem_duplicar_codigo(self):
        simulado = self.criar_simulado()
        importar_json(simulado, json.dumps(self.payload()), self.staff, salvar_no_banco=True)
        self.assertEqual(simulado.questoes.count(), 1)
        self.assertTrue(Questao.objects.filter(codigo="JSON-001").exists())
        with self.assertRaises(ValidationError):
            importar_json(simulado, json.dumps(self.payload()), self.staff, salvar_no_banco=True)

    def test_alternativas_invalidas_cancelam_importacao(self):
        simulado = self.criar_simulado()
        payload = self.payload()
        payload["questoes"][0]["alternativas"][1]["correta"] = False
        with self.assertRaises(ValidationError):
            importar_json(simulado, json.dumps(payload), self.staff)
        self.assertEqual(simulado.questoes.count(), 0)


class TentativaSimuladoTests(SimuladoTestMixin, TestCase):
    def test_resposta_correta_e_calculada_no_servidor(self):
        simulado = self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        tentativa = TentativaSimulado.objects.create(usuario=self.estudante, simulado=simulado, total_questoes=1)
        questao = simulado.questoes.first()
        errada = self.primeira_alternativa(questao, correta=False)
        resposta = RespostaSimulado.objects.create(
            tentativa=tentativa,
            questao_simulado=questao,
            alternativa_escolhida=errada,
            correta=True,
        )
        self.assertFalse(resposta.correta)
        self.assertEqual(resposta.alternativa_chave, "B")

    def test_resultado_e_diagnostico_multiplos_conteudos(self):
        questao = self.criar_questao("MAT-002", conteudos=[self.conteudo, self.outro_conteudo])
        simulado = self.criar_simulado()
        criar_snapshot_de_questao(simulado, questao)
        simulado.publicar()
        tentativa = self.finalizar_com_resposta(simulado, correta=True)
        diag = diagnostico_tentativa(tentativa)
        self.assertEqual(tentativa.total_acertos, 1)
        self.assertEqual(tentativa.percentual, 100)
        self.assertEqual(len(diag), 2)
        self.assertTrue(all(item["acertos"] == 1 for item in diag))

    def test_nova_tentativa_nao_sobrescreve_antiga(self):
        simulado = self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        primeira = self.finalizar_com_resposta(simulado, correta=True)
        segunda = TentativaSimulado.objects.create(usuario=self.estudante, simulado=simulado, total_questoes=1)
        self.assertNotEqual(primeira.pk, segunda.pk)
        self.assertEqual(TentativaSimulado.objects.filter(usuario=self.estudante, simulado=simulado).count(), 2)

    def test_resposta_finalizada_fica_imutavel(self):
        tentativa = self.finalizar_com_resposta(correta=True)
        resposta = tentativa.respostas.first()
        resposta.alternativa_escolhida = self.primeira_alternativa(resposta.questao_simulado, correta=False)
        with self.assertRaises(ValidationError):
            resposta.save()

    def test_simulado_com_tentativa_bloqueia_alteracao_estrutural(self):
        simulado = self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        self.finalizar_com_resposta(simulado, correta=True)
        with self.assertRaises(ValidationError):
            criar_snapshot_de_questao(simulado, self.criar_questao("MAT-003"))


class SimuladoViewTests(SimuladoTestMixin, TestCase):
    def test_estudante_nao_acessa_tentativa_de_outro_usuario(self):
        tentativa = self.finalizar_com_resposta(correta=True)
        self.client.force_login(self.outro_estudante)
        response = self.client.get(reverse("simulados:resultado_tentativa", args=[tentativa.pk]))
        self.assertEqual(response.status_code, 404)

    def test_fluxo_historico_e_refazer(self):
        simulado = self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        self.client.force_login(self.estudante)
        self.client.post(reverse("simulados:iniciar_simulado", args=[simulado.slug]))
        tentativa = TentativaSimulado.objects.get(usuario=self.estudante, simulado=simulado)
        questao = simulado.questoes.first()
        self.client.post(
            reverse("simulados:tentativa_questao", args=[tentativa.pk, 1]),
            {"alternativa": self.primeira_alternativa(questao, correta=True).pk, "acao": "finalizar"},
        )
        self.client.post(reverse("simulados:finalizar_tentativa", args=[tentativa.pk]))
        response = self.client.get(reverse("simulados:meus_simulados"))
        self.assertContains(response, "100,00%")
        self.client.post(reverse("simulados:iniciar_simulado", args=[simulado.slug]))
        self.assertEqual(TentativaSimulado.objects.filter(usuario=self.estudante, simulado=simulado).count(), 2)

    def test_minha_lista_aceita_simulado_e_constraint_continua_exatamente_um_alvo(self):
        simulado = self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        ItemMinhaLista.objects.create(usuario=self.estudante, simulado=simulado)
        self.assertEqual(ItemMinhaLista.objects.get(usuario=self.estudante).tipo_display, "Simulado")
        with self.assertRaises(ValidationError):
            ItemMinhaLista(usuario=self.estudante, simulado=simulado, materia=self.matematica).full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ItemMinhaLista.objects.create(usuario=self.estudante, simulado=simulado)

    def test_admin_requer_staff(self):
        self.client.force_login(self.estudante)
        response = self.client.get(reverse("simulados_admin:admin_simulados_lista"))
        self.assertEqual(response.status_code, 403)

    def test_admin_publica_rascunhos_validos_e_mantem_invalidos(self):
        valido = self.criar_simulado()
        criar_snapshot_de_questao(valido, self.criar_questao("MAT-010"))
        invalido = self.criar_simulado()
        arquivado = self.criar_simulado()
        arquivado.status = Simulado.StatusSimulado.ARQUIVADO
        arquivado.save(update_fields=["status", "atualizado_em"])
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("simulados_admin:admin_simulados_publicar_rascunhos"),
            follow=True,
        )

        valido.refresh_from_db()
        invalido.refresh_from_db()
        arquivado.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(valido.status, Simulado.StatusSimulado.PUBLICADO)
        self.assertEqual(invalido.status, Simulado.StatusSimulado.RASCUNHO)
        self.assertEqual(arquivado.status, Simulado.StatusSimulado.ARQUIVADO)

    def test_revisao_nao_envia_gabarito_ou_explicacao(self):
        tentativa = self.finalizar_com_resposta(correta=False)
        self.client.force_login(self.estudante)
        response = self.client.get(reverse("simulados:revisao_tentativa", args=[tentativa.pk]))
        self.assertContains(response, "Você errou")
        self.assertNotContains(response, "Explicação que pode revelar")
        self.assertNotContains(response, "correta=True")
        self.assertNotContains(response, "alternativa-correta")
        self.assertNotContains(response, "data-correta")
