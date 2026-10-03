import json
from unittest.mock import patch

import cloudinary
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from curriculo.models import Conteudo, Materia
from estudos.models import ItemMinhaLista
from questoes.models import Alternativa, Questao, QuestaoConteudo

from .models import AlternativaSimulado, QuestaoSimulado, RespostaSimulado, Simulado, TentativaSimulado
from .services import (
    conteudos_que_merecem_atencao,
    criar_snapshot_de_questao,
    diagnostico_tentativa,
    importar_json,
)


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
        self.matematica = Materia.objects.create(
            nome="Matemática",
            slug="matematica",
            descricao="Disciplina de matemática.",
            ordem_exibicao=1,
        )
        self.fisica = Materia.objects.create(
            nome="Física",
            slug="fisica",
            descricao="Disciplina de física.",
            ordem_exibicao=2,
        )
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
        questao.imagem_public_id = "enem/2025/c7/q136"
        questao.imagem_alt = "Imagem original"
        questao.save(update_fields=["imagem_public_id", "imagem_alt", "atualizado_em"])
        alternativa = questao.alternativas.get(chave="A")
        alternativa.imagem_public_id = "enem/2025/c7/q136-a"
        alternativa.imagem_alt = "Alternativa original"
        alternativa.save(update_fields=["imagem_public_id", "imagem_alt"])
        simulado = self.criar_simulado()
        snapshot = criar_snapshot_de_questao(simulado, questao)

        questao.enunciado = "Enunciado alterado"
        questao.explicacao = "Explicação alterada"
        questao.imagem_public_id = "enem/2025/c7/q136-v2"
        questao.imagem_alt = "Imagem alterada"
        questao.status = Questao.StatusQuestao.ARQUIVADA
        questao.save()
        questao.alternativas.filter(chave="A").update(texto="Correta alterada", correta=False)
        questao.alternativas.filter(chave="B").update(correta=True)
        questao.delete()

        snapshot.refresh_from_db()
        self.assertEqual(snapshot.enunciado, "Enunciado MAT-001")
        self.assertEqual(snapshot.explicacao, "Explicação que pode revelar a resposta correta.")
        self.assertEqual(snapshot.imagem_public_id, "enem/2025/c7/q136")
        self.assertEqual(snapshot.imagem_alt, "Imagem original")
        cloudinary.config(cloud_name="demo", secure=True)
        self.assertIn("https://res.cloudinary.com/demo/image/upload", snapshot.imagem_url)
        self.assertIn("enem/2025/c7/q136", snapshot.imagem_url)
        self.assertIsNone(snapshot.questao_origem)
        self.assertEqual(snapshot.alternativas.get(chave="A").texto, "Correta original")
        self.assertTrue(snapshot.alternativas.get(chave="A").correta)
        self.assertEqual(snapshot.alternativas.get(chave="A").imagem_public_id, "enem/2025/c7/q136-a")
        self.assertIn("enem/2025/c7/q136-a", snapshot.alternativas.get(chave="A").imagem_url)

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

    @patch("simulados.services.validar_public_id")
    def test_importacao_json_de_simulado_aceita_imagens_e_salva_no_banco(self, validar_mock):
        simulado = self.criar_simulado()
        payload = self.payload("JSON-IMG")
        payload["questoes"][0]["imagem"] = {
            "public_id": "enem/2025/caderno7/q136",
            "alt": "Imagem da questão",
        }
        payload["questoes"][0]["alternativas"][0]["imagem"] = {
            "public_id": "enem/2025/caderno7/q136-a",
            "alt": "Imagem da alternativa A",
        }
        payload["questoes"][0]["alternativas"][0]["texto"] = ""

        importar_json(simulado, json.dumps(payload), self.staff, salvar_no_banco=True)

        snapshot = simulado.questoes.get()
        questao_banco = Questao.objects.get(codigo="JSON-IMG")
        self.assertEqual(snapshot.imagem_public_id, "enem/2025/caderno7/q136")
        self.assertEqual(snapshot.alternativas.get(chave="A").imagem_public_id, "enem/2025/caderno7/q136-a")
        self.assertEqual(questao_banco.imagem_public_id, "enem/2025/caderno7/q136")
        self.assertEqual(questao_banco.alternativas.get(chave="A").imagem_public_id, "enem/2025/caderno7/q136-a")
        self.assertEqual(validar_mock.call_count, 2)

    @patch("simulados.services.validar_public_id")
    def test_importacao_json_de_simulado_aceita_public_id_simples_e_requer_imagem_valido(self, validar_mock):
        simulado = self.criar_simulado()
        payload = self.payload("JSON-IMG-SIMPLES")
        payload["questoes"][0]["requer_imagem"] = True
        payload["questoes"][0]["imagem"] = {"public_id": "abc123", "alt": "Imagem simples"}

        importar_json(simulado, json.dumps(payload), self.staff, salvar_no_banco=True)

        snapshot = simulado.questoes.get()
        questao_banco = Questao.objects.get(codigo="JSON-IMG-SIMPLES")
        self.assertEqual(snapshot.imagem_public_id, "abc123")
        self.assertEqual(questao_banco.imagem_public_id, "abc123")
        validar_mock.assert_called_once_with("abc123")

    def test_importacao_json_de_simulado_rejeita_requer_imagem_sem_public_id(self):
        simulado = self.criar_simulado()
        payload = self.payload("JSON-IMG-OBRIGATORIA")
        payload["questoes"][0]["requer_imagem"] = True

        with self.assertRaises(ValidationError) as ctx:
            importar_json(simulado, json.dumps(payload), self.staff)

        self.assertIn("requer imagem", str(ctx.exception))
        self.assertEqual(simulado.questoes.count(), 0)

    @patch("simulados.services.validar_public_id", side_effect=ValidationError('Imagem Cloudinary "nao-existe" não encontrada.'))
    def test_importacao_json_de_simulado_com_public_id_inexistente_faz_rollback(self, validar_mock):
        simulado = self.criar_simulado()
        payload = self.payload("JSON-IMG-INVALIDA")
        payload["questoes"][0]["imagem"] = {"public_id": "nao-existe", "alt": ""}

        with self.assertRaises(ValidationError):
            importar_json(simulado, json.dumps(payload), self.staff)

        self.assertEqual(simulado.questoes.count(), 0)
        self.assertFalse(Questao.objects.filter(codigo="JSON-IMG-INVALIDA").exists())
        validar_mock.assert_called_once_with("nao-existe")

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

    def test_execucao_e_revisao_do_simulado_exibem_imagens_do_snapshot(self):
        cloudinary.config(cloud_name="demo", secure=True)
        questao = self.criar_questao("MAT-IMG-SIM")
        questao.imagem_public_id = "enem/2025/caderno7/q136"
        questao.imagem_alt = "Imagem da questão"
        questao.save(update_fields=["imagem_public_id", "imagem_alt", "atualizado_em"])
        alternativa = questao.alternativas.get(chave="A")
        alternativa.imagem_public_id = "enem/2025/caderno7/q136-a"
        alternativa.imagem_alt = "Imagem da alternativa A"
        alternativa.save(update_fields=["imagem_public_id", "imagem_alt"])
        simulado = self.criar_simulado()
        snapshot = criar_snapshot_de_questao(simulado, questao)
        simulado.publicar()
        url_questao = "https://res.cloudinary.com/demo/image/upload/v1/enem/2025/caderno7/q136"
        url_alternativa = "https://res.cloudinary.com/demo/image/upload/v1/enem/2025/caderno7/q136-a"
        self.client.force_login(self.estudante)

        self.client.post(reverse("simulados:iniciar_simulado", args=[simulado.slug]))
        tentativa = TentativaSimulado.objects.get(usuario=self.estudante, simulado=simulado)
        execucao = self.client.get(reverse("simulados:tentativa_questao", args=[tentativa.pk, 1]))
        self.assertContains(execucao, f'src="{url_questao}"')
        self.assertContains(execucao, f'alt="{questao.imagem_alt}"')
        self.assertContains(execucao, f'src="{url_alternativa}"')
        self.assertContains(execucao, f'alt="{alternativa.imagem_alt}"')

        self.client.post(
            reverse("simulados:tentativa_questao", args=[tentativa.pk, 1]),
            {"alternativa": snapshot.alternativas.get(chave="A").pk, "acao": "finalizar"},
        )
        self.client.post(reverse("simulados:finalizar_tentativa", args=[tentativa.pk]))
        revisao = self.client.get(reverse("simulados:revisao_tentativa", args=[tentativa.pk]))
        self.assertContains(revisao, f'src="{url_questao}"')
        self.assertContains(revisao, f'src="{url_alternativa}"')

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


class NavegacaoVoltarSimuladoTests(SimuladoTestMixin, TestCase):
    def test_paginas_da_tentativa_nao_ficam_em_cache(self):
        simulado = self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        self.client.force_login(self.estudante)
        self.client.post(reverse("simulados:iniciar_simulado", args=[simulado.slug]))
        tentativa = TentativaSimulado.objects.get(usuario=self.estudante, simulado=simulado)
        for url in (
            reverse("simulados:tentativa_questao", args=[tentativa.pk, 1]),
            reverse("simulados:finalizar_tentativa", args=[tentativa.pk]),
        ):
            self.assertIn("no-store", self.client.get(url)["Cache-Control"])

    def test_voltar_da_tentativa_sai_para_meus_simulados(self):
        simulado = self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        self.client.force_login(self.estudante)
        self.client.post(reverse("simulados:iniciar_simulado", args=[simulado.slug]))
        tentativa = TentativaSimulado.objects.get(usuario=self.estudante, simulado=simulado)
        response = self.client.get(reverse("simulados:tentativa_questao", args=[tentativa.pk, 1]))
        self.assertContains(
            response,
            f'id="appBackButton" href="{reverse("simulados:meus_simulados")}"',
        )
        self.assertContains(response, "Sair do simulado")

    def test_voltar_do_resultado_nao_reabre_tentativa_finalizada(self):
        tentativa = self.finalizar_com_resposta(correta=True)
        self.client.force_login(self.estudante)
        resultado = self.client.get(reverse("simulados:resultado_tentativa", args=[tentativa.pk]))
        self.assertContains(
            resultado,
            f'id="appBackButton" href="{reverse("simulados:meus_simulados")}"',
        )
        finalizar = self.client.get(reverse("simulados:finalizar_tentativa", args=[tentativa.pk]))
        self.assertRedirects(finalizar, reverse("simulados:resultado_tentativa", args=[tentativa.pk]))


class BotoesStatusSimuladoTests(SimuladoTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def criar_simulado_arquivado(self):
        simulado = self.criar_simulado()
        simulado.status = Simulado.StatusSimulado.ARQUIVADO
        simulado.save(update_fields=["status", "atualizado_em"])
        return simulado

    def test_publicar_desabilitado_quando_simulado_ja_publicado(self):
        simulado = self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        response = self.client.get(reverse("simulados_admin:admin_simulado_detalhe", args=[simulado.pk]))
        self.assertContains(response, 'disabled title="Este simulado já está publicado."')
        self.assertNotContains(response, 'disabled title="Este simulado já está arquivado."')

    def test_arquivar_desabilitado_quando_simulado_ja_arquivado(self):
        simulado = self.criar_simulado_arquivado()
        response = self.client.get(reverse("simulados_admin:admin_simulado_detalhe", args=[simulado.pk]))
        self.assertContains(response, 'disabled title="Este simulado já está arquivado."')
        self.assertNotContains(response, 'disabled title="Este simulado já está publicado."')

    def test_rascunho_tem_publicar_e_arquivar_habilitados(self):
        simulado = self.criar_simulado()
        response = self.client.get(reverse("simulados_admin:admin_simulado_detalhe", args=[simulado.pk]))
        self.assertNotContains(response, "disabled title=")

    def test_publicar_novamente_nao_altera_simulado(self):
        simulado = self.criar_simulado(status=Simulado.StatusSimulado.PUBLICADO)
        atualizado_em = simulado.atualizado_em
        response = self.client.post(
            reverse("simulados_admin:admin_simulado_publicar", args=[simulado.pk]),
            follow=True,
        )
        self.assertContains(response, "Este simulado já está publicado.")
        simulado.refresh_from_db()
        self.assertEqual(simulado.atualizado_em, atualizado_em)

    def test_arquivar_novamente_nao_altera_simulado(self):
        simulado = self.criar_simulado_arquivado()
        atualizado_em = simulado.atualizado_em
        response = self.client.post(
            reverse("simulados_admin:admin_simulado_arquivar", args=[simulado.pk]),
            follow=True,
        )
        self.assertContains(response, "Este simulado já está arquivado.")
        simulado.refresh_from_db()
        self.assertEqual(simulado.atualizado_em, atualizado_em)


class ConteudosQueMerecemAtencaoTests(SimpleTestCase):
    def diagnostico(self, *percentuais):
        return [{"titulo": f"Conteúdo {indice}", "percentual": percentual} for indice, percentual in enumerate(sorted(percentuais))]

    def percentuais(self, itens):
        return [item["percentual"] for item in itens]

    def test_mostra_todos_os_conteudos_abaixo_de_60(self):
        atencao = conteudos_que_merecem_atencao(self.diagnostico(0, 20, 40, 50, 59.99, 60, 80))
        self.assertEqual(self.percentuais(atencao), [0, 20, 40, 50, 59.99])

    def test_sem_conteudo_abaixo_de_60_mostra_os_tres_menores(self):
        atencao = conteudos_que_merecem_atencao(self.diagnostico(60, 70, 75, 80, 90, 100))
        self.assertEqual(self.percentuais(atencao), [60, 70, 75])

    def test_empate_no_ultimo_lugar_mostra_todos_os_empatados(self):
        atencao = conteudos_que_merecem_atencao(self.diagnostico(60, 70, 75, 75, 75, 90))
        self.assertEqual(self.percentuais(atencao), [60, 70, 75, 75, 75])

    def test_conteudos_com_100_nunca_aparecem_entre_os_menores(self):
        atencao = conteudos_que_merecem_atencao(self.diagnostico(80, 100, 100, 100))
        self.assertEqual(self.percentuais(atencao), [80])

    def test_todos_com_100_nao_mostra_nenhum(self):
        self.assertEqual(conteudos_que_merecem_atencao(self.diagnostico(100, 100)), [])


class ResultadoSimuladoAtencaoTests(SimuladoTestMixin, TestCase):
    def test_aproveitamento_total_mostra_parabens(self):
        tentativa = self.finalizar_com_resposta(correta=True)
        self.client.force_login(self.estudante)
        response = self.client.get(reverse("simulados:resultado_tentativa", args=[tentativa.pk]))
        self.assertContains(response, "Parabéns!")
        self.assertNotContains(response, "Revisar conteúdo")

    def test_conteudo_abaixo_de_60_aparece_para_revisao(self):
        tentativa = self.finalizar_com_resposta(correta=False)
        self.client.force_login(self.estudante)
        response = self.client.get(reverse("simulados:resultado_tentativa", args=[tentativa.pk]))
        self.assertNotContains(response, "Parabéns!")
        self.assertContains(response, "Revisar conteúdo")
        self.assertEqual(len(response.context["atencao"]), 1)
