from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
import json
from unittest.mock import patch

import cloudinary
from curriculo.models import Conteudo, Materia
from django.core.files.uploadedfile import SimpleUploadedFile

from .imagens import (
    TAMANHO_MAXIMO_BYTES,
    _validar_resultado_cloudinary,
    gerar_url_imagem,
    upload_imagem_arquivo,
    validar_url_imagem,
)
from .models import Alternativa, Questao, QuestaoConteudo, RespostaQuestao


Usuario = get_user_model()


class QuestaoTestMixin:
    def setUp(self):
        self.estudante = Usuario.objects.create_user(
            email="aluno@example.com",
            password="SenhaForte123",
            first_name="Aluno",
        )
        self.staff = Usuario.objects.create_user(
            email="admin@example.com",
            password="SenhaForte123",
            first_name="Admin",
            is_staff=True,
        )
        self.superuser = Usuario.objects.create_superuser(
            email="super@example.com",
            password="SenhaForte123",
            first_name="Super",
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
        self.conteudo = self.criar_conteudo("Porcentagem", self.matematica)
        self.outro_conteudo = self.criar_conteudo("Razão e proporção", self.matematica)
        self.conteudo_fisica = self.criar_conteudo("Cinemática", self.fisica)

    def criar_conteudo(
        self,
        titulo,
        materia,
        status=Conteudo.StatusConteudo.PUBLICADO,
    ):
        return Conteudo.objects.create(
            materia=materia,
            titulo=titulo,
            resumo=f"Resumo de {titulo}",
            status=status,
            criado_por=self.staff,
        )

    def criar_questao(
        self,
        codigo="MAT-001",
        materia=None,
        status=Questao.StatusQuestao.PUBLICADA,
        dificuldade=Questao.DificuldadeQuestao.MEDIA,
        conteudos=None,
        explicacao="Explicação da questão.",
    ):
        materia = materia or self.matematica
        conteudos = list(conteudos or [self.conteudo])
        questao = Questao.objects.create(
            codigo=codigo,
            materia=materia,
            enunciado=f"Enunciado da questão {codigo}",
            explicacao=explicacao,
            dificuldade=dificuldade,
            status=Questao.StatusQuestao.RASCUNHO,
            criado_por=self.staff,
        )
        Alternativa.objects.create(
            questao=questao,
            chave="A",
            texto="Alternativa correta",
            correta=True,
            ordem=1,
        )
        Alternativa.objects.create(
            questao=questao,
            chave="B",
            texto="Alternativa incorreta",
            correta=False,
            ordem=2,
        )
        for indice, conteudo in enumerate(conteudos):
            QuestaoConteudo.objects.create(
                questao=questao,
                conteudo=conteudo,
                principal=indice == 0,
            )
        if status == Questao.StatusQuestao.PUBLICADA:
            questao.publicar()
        elif status != Questao.StatusQuestao.RASCUNHO:
            questao.status = status
            questao.save(update_fields=["status", "atualizado_em"])
        return questao

    def alternativa(self, questao, correta=True):
        return questao.alternativas.get(correta=correta)


class QuestaoModelTests(QuestaoTestMixin, TestCase):
    def test_criacao_valida_uuid_defaults_e_str(self):
        questao = Questao.objects.create(
            codigo=" mat-010 ",
            materia=self.matematica,
            enunciado="  Quanto é 2 + 2? ",
            criado_por=self.staff,
        )

        self.assertIsNotNone(questao.id)
        self.assertEqual(questao.codigo, "MAT-010")
        self.assertEqual(questao.dificuldade, Questao.DificuldadeQuestao.MEDIA)
        self.assertEqual(questao.status, Questao.StatusQuestao.RASCUNHO)
        self.assertEqual(questao.materia, self.matematica)
        self.assertEqual(str(questao), "MAT-010")

    def test_questao_exige_codigo_e_enunciado(self):
        questao = Questao(codigo=" ", materia=self.matematica, enunciado=" ")

        with self.assertRaises(ValidationError):
            questao.full_clean()

    def test_questao_sem_imagem_continua_valida(self):
        questao = Questao(codigo="MAT-010-SEM-IMG", materia=self.matematica, enunciado="Enunciado")

        questao.full_clean()

        self.assertEqual(questao.imagem_public_id, "")

    def test_alternativa_constraints_por_questao(self):
        questao = self.criar_questao("MAT-011")
        outra = self.criar_questao("MAT-012")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Alternativa.objects.create(
                    questao=questao,
                    chave="A",
                    texto="Duplicada",
                    ordem=3,
                )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Alternativa.objects.create(
                    questao=questao,
                    chave="C",
                    texto="Ordem duplicada",
                    ordem=1,
                )

        self.assertTrue(outra.alternativas.filter(chave="A").exists())

    def test_alternativa_aceita_texto_texto_com_imagem_ou_somente_imagem(self):
        questao = Questao.objects.create(
            codigo="MAT-012-IMG",
            materia=self.matematica,
            enunciado="Enunciado",
        )

        Alternativa(questao=questao, chave="A", texto="Texto", ordem=1).full_clean()
        Alternativa(
            questao=questao,
            chave="B",
            texto="Texto",
            imagem_public_id="plataforma-estudos/alternativas/b",
            ordem=2,
        ).full_clean()
        Alternativa(
            questao=questao,
            chave="C",
            texto="",
            imagem_public_id="plataforma-estudos/alternativas/c",
            ordem=3,
        ).full_clean()
        with self.assertRaises(ValidationError):
            Alternativa(questao=questao, chave="D", texto="", ordem=4).full_clean()

    def test_url_cloudinary_e_gerada_a_partir_de_public_id(self):
        cloudinary.config(cloud_name="demo")
        questao = Questao(
            codigo="MAT-012-URL",
            materia=self.matematica,
            enunciado="Enunciado",
            imagem_public_id="enem/2025/caderno7/q136",
        )

        self.assertIn("enem/2025/caderno7/q136", questao.imagem_url)
        self.assertEqual(questao.imagem_alt_texto, "Imagem da questão")


class ImagemSegurancaTests(QuestaoTestMixin, TestCase):
    @patch("questoes.imagens.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))])
    def test_valida_url_http_https_e_bloqueia_rede_local(self, getaddrinfo_mock):
        self.assertEqual(validar_url_imagem("https://example.com/imagem.png"), "https://example.com/imagem.png")
        with self.assertRaises(ValidationError):
            validar_url_imagem("ftp://example.com/imagem.png")
        with self.assertRaises(ValidationError):
            validar_url_imagem("http://127.0.0.1/imagem.png")
        with self.assertRaises(ValidationError):
            validar_url_imagem("http://localhost/imagem.png")
        getaddrinfo_mock.assert_called_once()

    def test_geracao_de_url_nao_expoe_credenciais(self):
        cloudinary.config(cloud_name="demo")
        url = gerar_url_imagem("enem/2025/caderno7/q136")

        self.assertIn("https://", url)
        self.assertIn("res.cloudinary.com/demo/image/upload", url)
        self.assertIn("enem/2025/caderno7/q136", url)
        self.assertNotIn("api_secret", url.lower())

    def test_validacao_resultado_cloudinary_retorna_public_id_oficial(self):
        resultado = {
            "resource_type": "image",
            "format": "png",
            "bytes": 1234,
            "asset_id": "asset-id-nao-persistir",
            "secure_url": "https://res.cloudinary.com/demo/image/upload/errado.png",
            "original_filename": "arquivo-local",
            "public_id": "plataforma-estudos/questoes/public-id-oficial",
        }

        self.assertEqual(
            _validar_resultado_cloudinary(resultado),
            "plataforma-estudos/questoes/public-id-oficial",
        )

    @patch("questoes.imagens.cloudinary.uploader.upload")
    def test_upload_arquivo_salva_public_id_e_nao_asset_id_ou_secure_url(self, upload_mock):
        upload_mock.return_value = {
            "resource_type": "image",
            "format": "webp",
            "bytes": 1234,
            "asset_id": "asset-id-nao-persistir",
            "secure_url": "https://res.cloudinary.com/demo/image/upload/nao-salvar",
            "public_id": "plataforma-estudos/questoes/public-id-retornado",
        }
        arquivo = SimpleUploadedFile("questao.webp", b"conteudo", content_type="image/webp")

        public_id = upload_imagem_arquivo(arquivo)

        self.assertEqual(public_id, "plataforma-estudos/questoes/public-id-retornado")
        self.assertNotEqual(public_id, upload_mock.return_value["asset_id"])
        self.assertNotEqual(public_id, upload_mock.return_value["secure_url"])
        public_id_enviado = upload_mock.call_args.kwargs["public_id"]
        self.assertTrue(public_id_enviado.startswith("plataforma-estudos/questoes/"))
        self.assertNotIn("/questoes/questoes/", public_id_enviado)

    def test_upload_rejeita_svg_e_arquivo_maior_que_limite(self):
        svg = SimpleUploadedFile("imagem.svg", b"<svg></svg>", content_type="image/svg+xml")
        grande = SimpleUploadedFile(
            "imagem.png",
            b"x" * (TAMANHO_MAXIMO_BYTES + 1),
            content_type="image/png",
        )

        with self.assertRaises(ValidationError):
            upload_imagem_arquivo(svg)
        with self.assertRaises(ValidationError):
            upload_imagem_arquivo(grande)

    def test_questaoconteudo_valida_materia_e_duplicidade(self):
        questao = self.criar_questao("MAT-013")
        relacao = QuestaoConteudo(questao=questao, conteudo=self.conteudo_fisica)

        with self.assertRaises(ValidationError):
            relacao.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QuestaoConteudo.objects.create(questao=questao, conteudo=self.conteudo)

    def test_questaoconteudo_no_maximo_um_principal(self):
        questao = self.criar_questao("MAT-014", conteudos=[self.conteudo])

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QuestaoConteudo.objects.create(
                    questao=questao,
                    conteudo=self.outro_conteudo,
                    principal=True,
                )

    def test_validacao_de_publicacao(self):
        sem_alternativas = Questao.objects.create(
            codigo="MAT-015",
            materia=self.matematica,
            enunciado="Sem alternativas",
        )
        with self.assertRaises(ValidationError):
            sem_alternativas.publicar()

        uma_alternativa = Questao.objects.create(
            codigo="MAT-016",
            materia=self.matematica,
            enunciado="Uma alternativa",
        )
        Alternativa.objects.create(questao=uma_alternativa, chave="A", texto="A", correta=True, ordem=1)
        QuestaoConteudo.objects.create(questao=uma_alternativa, conteudo=self.conteudo)
        with self.assertRaises(ValidationError):
            uma_alternativa.publicar()

        sem_correta = self.criar_questao("MAT-017", status=Questao.StatusQuestao.RASCUNHO)
        sem_correta.alternativas.update(correta=False)
        with self.assertRaises(ValidationError):
            sem_correta.publicar()

        duas_corretas = self.criar_questao("MAT-018", status=Questao.StatusQuestao.RASCUNHO)
        duas_corretas.alternativas.update(correta=True)
        with self.assertRaises(ValidationError):
            duas_corretas.publicar()

        sem_conteudo = self.criar_questao("MAT-019", status=Questao.StatusQuestao.RASCUNHO)
        sem_conteudo.questao_conteudos.all().delete()
        with self.assertRaises(ValidationError):
            sem_conteudo.publicar()

        sem_principal = self.criar_questao("MAT-020A", status=Questao.StatusQuestao.RASCUNHO)
        sem_principal.questao_conteudos.update(principal=False)
        with self.assertRaises(ValidationError):
            sem_principal.publicar()

        valida = self.criar_questao("MAT-020", status=Questao.StatusQuestao.RASCUNHO)
        valida.publicar()
        self.assertEqual(valida.status, Questao.StatusQuestao.PUBLICADA)


class RespostaQuestaoTests(QuestaoTestMixin, TestCase):
    def test_resposta_calcula_resultado_no_servidor(self):
        questao = self.criar_questao("MAT-021")
        correta = self.alternativa(questao, correta=True)
        errada = self.alternativa(questao, correta=False)

        resposta_correta = RespostaQuestao.objects.create(
            usuario=self.estudante,
            questao=questao,
            alternativa_escolhida=correta,
            correta=False,
        )
        resposta_errada = RespostaQuestao.objects.create(
            usuario=self.estudante,
            questao=questao,
            alternativa_escolhida=errada,
            correta=True,
        )

        self.assertTrue(resposta_correta.correta)
        self.assertFalse(resposta_errada.correta)
        self.assertEqual(RespostaQuestao.objects.filter(questao=questao).count(), 2)

    def test_alternativa_de_outra_questao_e_rejeitada(self):
        questao = self.criar_questao("MAT-022")
        outra = self.criar_questao("MAT-023")
        resposta = RespostaQuestao(
            usuario=self.estudante,
            questao=questao,
            alternativa_escolhida=self.alternativa(outra, correta=True),
            correta=False,
        )

        with self.assertRaises(ValidationError):
            resposta.full_clean()


class EstudanteQuestaoViewTests(QuestaoTestMixin, TestCase):
    def test_visitante_nao_acessa_e_estudante_ve_apenas_publicadas(self):
        publicada = self.criar_questao("MAT-024")
        rascunho = self.criar_questao("MAT-025", status=Questao.StatusQuestao.RASCUNHO)
        arquivada = self.criar_questao("MAT-026", status=Questao.StatusQuestao.ARQUIVADA)

        response = self.client.get(reverse("questoes:exercicios_lista"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.estudante)
        response = self.client.get(reverse("questoes:exercicios_lista"))
        self.assertContains(response, publicada.codigo)
        self.assertNotContains(response, rascunho.codigo)
        self.assertNotContains(response, arquivada.codigo)

    def test_filtros_e_ordenacao_da_listagem(self):
        facil_um = self.criar_questao(
            "MAT-027",
            dificuldade=Questao.DificuldadeQuestao.FACIL,
            conteudos=[self.conteudo],
        )
        facil_dois = self.criar_questao(
            "MAT-028",
            dificuldade=Questao.DificuldadeQuestao.FACIL,
            conteudos=[self.conteudo, self.outro_conteudo],
        )
        media = self.criar_questao(
            "MAT-029",
            dificuldade=Questao.DificuldadeQuestao.MEDIA,
            conteudos=[self.outro_conteudo],
        )
        dificil = self.criar_questao(
            "MAT-030",
            dificuldade=Questao.DificuldadeQuestao.DIFICIL,
            conteudos=[self.outro_conteudo],
        )
        self.client.force_login(self.estudante)

        response = self.client.get(reverse("questoes:exercicios_lista"))
        codigos = [questao.codigo for questao in response.context["page_obj"]]
        self.assertLess(codigos.index(facil_um.codigo), codigos.index(facil_dois.codigo))
        self.assertLess(codigos.index(facil_dois.codigo), codigos.index(media.codigo))
        self.assertLess(codigos.index(media.codigo), codigos.index(dificil.codigo))

        response = self.client.get(
            reverse("questoes:exercicios_lista"),
            {"materia": self.matematica.slug, "conteudo": str(self.outro_conteudo.pk), "dificuldade": Questao.DificuldadeQuestao.MEDIA},
        )
        self.assertContains(response, media.codigo)
        self.assertNotContains(response, facil_um.codigo)
        self.assertNotContains(response, dificil.codigo)

    def test_detalhe_resposta_e_historico(self):
        questao = self.criar_questao("MAT-031")
        self.client.force_login(self.estudante)
        response = self.client.post(
            reverse("questoes:questao_detalhe", args=[questao.pk]),
            {"alternativa": self.alternativa(questao, correta=True).pk},
        )

        self.assertContains(response, "Você acertou")
        resposta = RespostaQuestao.objects.get(usuario=self.estudante, questao=questao)
        historico = self.client.get(reverse("questoes:historico"))
        self.assertContains(historico, questao.codigo)
        detalhe = self.client.get(reverse("questoes:resposta_detalhe", args=[resposta.pk]))
        self.assertContains(detalhe, "Escolhida")
        self.assertContains(detalhe, "Correta")
        self.assertContains(detalhe, "Explicação da questão")

    def test_aluno_ve_imagens_na_resolucao_resultado_sequencia_e_detalhe(self):
        cloudinary.config(cloud_name="demo", secure=True)
        questao = self.criar_questao("MAT-031-IMG")
        questao.imagem_public_id = "enem/2025/caderno7/q136"
        questao.imagem_alt = "Gráfico da questão"
        questao.save(update_fields=["imagem_public_id", "imagem_alt", "atualizado_em"])
        alternativa_imagem = questao.alternativas.get(chave="B")
        alternativa_imagem.texto = ""
        alternativa_imagem.imagem_public_id = "enem/2025/caderno7/q136-b"
        alternativa_imagem.imagem_alt = "Alternativa B"
        alternativa_imagem.save(update_fields=["texto", "imagem_public_id", "imagem_alt"])
        url_questao = "https://res.cloudinary.com/demo/image/upload/v1/enem/2025/caderno7/q136"
        url_alternativa = "https://res.cloudinary.com/demo/image/upload/v1/enem/2025/caderno7/q136-b"
        self.client.force_login(self.estudante)

        detalhe = self.client.get(reverse("questoes:questao_detalhe", args=[questao.pk]))
        self.assertContains(detalhe, f'src="{url_questao}"')
        self.assertContains(detalhe, f'alt="{questao.imagem_alt}"')
        self.assertContains(detalhe, f'src="{url_alternativa}"')
        self.assertContains(detalhe, f'alt="{alternativa_imagem.imagem_alt}"')

        resultado = self.client.post(
            reverse("questoes:questao_detalhe", args=[questao.pk]),
            {"alternativa": alternativa_imagem.pk},
        )
        self.assertContains(resultado, f'src="{url_questao}"')
        resposta = RespostaQuestao.objects.get(usuario=self.estudante, questao=questao)
        resposta_detalhe = self.client.get(reverse("questoes:resposta_detalhe", args=[resposta.pk]))
        self.assertContains(resposta_detalhe, f'src="{url_questao}"')
        self.assertContains(resposta_detalhe, f'src="{url_alternativa}"')

        self.client.get(reverse("questoes:iniciar_sequencia"))
        sequencia = self.client.get(reverse("questoes:sequencia"))
        self.assertContains(sequencia, f'src="{url_questao}"')
        self.assertContains(sequencia, f'src="{url_alternativa}"')
        sequencia_resultado = self.client.post(
            reverse("questoes:sequencia"),
            {"alternativa": alternativa_imagem.pk},
        )
        self.assertContains(sequencia_resultado, f'src="{url_questao}"')

    def test_historico_isola_respostas_por_usuario(self):
        questao = self.criar_questao("MAT-032")
        outro = Usuario.objects.create_user(
            email="outro@example.com",
            password="SenhaForte123",
            first_name="Outro",
        )
        resposta_outro = RespostaQuestao.objects.create(
            usuario=outro,
            questao=questao,
            alternativa_escolhida=self.alternativa(questao, correta=True),
            correta=False,
        )
        RespostaQuestao.objects.create(
            usuario=self.estudante,
            questao=questao,
            alternativa_escolhida=self.alternativa(questao, correta=False),
            correta=True,
        )

        self.client.force_login(self.estudante)
        historico = self.client.get(reverse("questoes:historico"))
        self.assertEqual(len(historico.context["page_obj"].object_list), 1)
        detalhe = self.client.get(reverse("questoes:resposta_detalhe", args=[resposta_outro.pk]))
        self.assertEqual(detalhe.status_code, 404)

    def test_questoes_indisponiveis_retorna_404(self):
        rascunho = self.criar_questao("MAT-033", status=Questao.StatusQuestao.RASCUNHO)
        arquivada = self.criar_questao("MAT-034", status=Questao.StatusQuestao.ARQUIVADA)
        inativa = Materia.objects.create(nome="Biologia", ativa=False)
        conteudo_inativo = self.criar_conteudo("Genética", inativa)
        questao_inativa = self.criar_questao(
            "BIO-001",
            materia=inativa,
            conteudos=[conteudo_inativo],
        )
        self.client.force_login(self.estudante)

        for questao in [rascunho, arquivada, questao_inativa]:
            response = self.client.get(reverse("questoes:questao_detalhe", args=[questao.pk]))
            self.assertEqual(response.status_code, 404)

    def test_acesso_via_conteudo_e_sequencia(self):
        questao = self.criar_questao("MAT-035")
        self.client.force_login(self.estudante)

        conteudo_response = self.client.get(
            reverse(
                "curriculo:conteudo_detalhe",
                args=[self.matematica.slug, self.conteudo.slug],
            )
        )
        self.assertContains(conteudo_response, f"conteudo={self.conteudo.pk}")

        inicio = self.client.get(
            reverse("questoes:iniciar_sequencia"),
            {"conteudo": str(self.conteudo.pk)},
        )
        self.assertRedirects(inicio, reverse("questoes:sequencia"))
        response = self.client.post(
            reverse("questoes:sequencia"),
            {"alternativa": self.alternativa(questao, correta=True).pk},
        )
        self.assertContains(response, "Você acertou")
        self.assertNotContains(response, "Correta")
        self.assertEqual(RespostaQuestao.objects.filter(usuario=self.estudante).count(), 1)
        resumo = self.client.get(reverse("questoes:sequencia"), follow=True)
        self.assertEqual(resumo.redirect_chain[-1][0], reverse("questoes:sequencia_resumo"))
        self.assertContains(resumo, "Questões respondidas")
        self.assertContains(resumo, "1")

    def test_estudante_nao_acessa_admin(self):
        self.client.force_login(self.estudante)
        response = self.client.get(reverse("questoes_admin:admin_questoes_lista"))
        self.assertEqual(response.status_code, 403)


class AdminQuestaoViewTests(QuestaoTestMixin, TestCase):
    def test_staff_e_superuser_acessam_admin(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("questoes_admin:admin_questoes_lista")).status_code, 200)
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(reverse("questoes_admin:admin_questoes_lista")).status_code, 200)

    def test_admin_cria_questao_com_alternativas_e_conteudo(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("questoes_admin:admin_questao_criar"),
            self._post_questao("MAT-036", status=Questao.StatusQuestao.PUBLICADA),
        )

        questao = Questao.objects.get(codigo="MAT-036")
        self.assertRedirects(
            response,
            reverse("questoes_admin:admin_questao_detalhe", args=[questao.pk]),
        )
        self.assertEqual(questao.criado_por, self.staff)
        self.assertEqual(questao.alternativas.count(), 2)
        self.assertEqual(questao.questao_conteudos.count(), 1)
        self.assertEqual(questao.status, Questao.StatusQuestao.PUBLICADA)

    def test_admin_cria_questao_com_ordem_automatica_de_alternativas(self):
        data = self._post_questao("MAT-036A", status=Questao.StatusQuestao.PUBLICADA)
        data["alternativas-0-ordem"] = ""
        data["alternativas-1-ordem"] = ""
        self.client.force_login(self.staff)

        response = self.client.post(reverse("questoes_admin:admin_questao_criar"), data)

        questao = Questao.objects.get(codigo="MAT-036A")
        self.assertRedirects(
            response,
            reverse("questoes_admin:admin_questao_detalhe", args=[questao.pk]),
        )
        self.assertEqual(
            list(questao.alternativas.order_by("ordem").values_list("chave", "ordem")),
            [("A", 1), ("B", 2)],
        )

    @patch("questoes.forms.upload_imagem_arquivo", return_value="plataforma-estudos/questoes/q1")
    def test_admin_cria_questao_com_upload_de_imagem(self, upload_mock):
        data = self._post_questao("MAT-036-IMG", status=Questao.StatusQuestao.RASCUNHO)
        data["imagem_alt"] = "Gráfico da questão"
        data["imagem_arquivo"] = SimpleUploadedFile("questao.png", b"conteudo", content_type="image/png")
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("questoes_admin:admin_questao_criar"),
            data,
        )

        questao = Questao.objects.get(codigo="MAT-036-IMG")
        self.assertRedirects(response, reverse("questoes_admin:admin_questao_detalhe", args=[questao.pk]))
        self.assertEqual(questao.imagem_public_id, "plataforma-estudos/questoes/q1")
        self.assertEqual(questao.imagem_alt, "Gráfico da questão")
        upload_mock.assert_called_once()

    @patch("questoes.forms.upload_imagem_url", return_value="plataforma-estudos/questoes/url")
    def test_admin_cria_questao_com_url_de_imagem(self, upload_mock):
        data = self._post_questao("MAT-036-URL", status=Questao.StatusQuestao.RASCUNHO)
        data["imagem_url"] = "https://example.com/imagem.png"
        self.client.force_login(self.staff)

        response = self.client.post(reverse("questoes_admin:admin_questao_criar"), data)

        questao = Questao.objects.get(codigo="MAT-036-URL")
        self.assertRedirects(response, reverse("questoes_admin:admin_questao_detalhe", args=[questao.pk]))
        self.assertEqual(questao.imagem_public_id, "plataforma-estudos/questoes/url")
        upload_mock.assert_called_once()

    def test_admin_rejeita_arquivo_e_url_simultaneos(self):
        data = self._post_questao("MAT-036-DUP", status=Questao.StatusQuestao.RASCUNHO)
        data["imagem_url"] = "https://example.com/imagem.png"
        data["imagem_arquivo"] = SimpleUploadedFile("questao.png", b"conteudo", content_type="image/png")
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("questoes_admin:admin_questao_criar"),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe uma imagem por arquivo ou por URL")
        self.assertFalse(Questao.objects.filter(codigo="MAT-036-DUP").exists())

    def test_admin_remove_associacao_de_imagem_sem_apagar_asset(self):
        questao = self.criar_questao("MAT-036-REMOVE")
        questao.imagem_public_id = "plataforma-estudos/questoes/antiga"
        questao.imagem_alt = "Imagem antiga"
        questao.save(update_fields=["imagem_public_id", "imagem_alt", "atualizado_em"])
        data = self._post_questao(
            "MAT-036-REMOVE",
            status=Questao.StatusQuestao.RASCUNHO,
            questao=questao,
        )
        data["remover_imagem"] = "on"
        self.client.force_login(self.staff)

        response = self.client.post(reverse("questoes_admin:admin_questao_editar", args=[questao.pk]), data)

        questao.refresh_from_db()
        self.assertRedirects(response, reverse("questoes_admin:admin_questao_detalhe", args=[questao.pk]))
        self.assertEqual(questao.imagem_public_id, "")
        self.assertEqual(questao.imagem_alt, "")

    @patch("questoes.forms.upload_imagem_url", side_effect=ValidationError("Não foi possível importar a imagem informada."))
    def test_falha_cloudinary_e_tratada_no_formulario(self, upload_mock):
        data = self._post_questao("MAT-036-FAIL", status=Questao.StatusQuestao.RASCUNHO)
        data["imagem_url"] = "https://example.com/imagem.png"
        self.client.force_login(self.staff)

        response = self.client.post(reverse("questoes_admin:admin_questao_criar"), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível importar a imagem informada.")
        self.assertFalse(Questao.objects.filter(codigo="MAT-036-FAIL").exists())
        upload_mock.assert_called_once()

    @patch("questoes.forms.upload_imagem_arquivo", return_value="plataforma-estudos/alternativas/a")
    def test_admin_cria_alternativa_somente_com_imagem(self, upload_mock):
        data = self._post_questao("MAT-036-ALTIMG", status=Questao.StatusQuestao.PUBLICADA)
        data["alternativas-1-texto"] = ""
        data["alternativas-1-imagem_arquivo"] = SimpleUploadedFile("alternativa.webp", b"conteudo", content_type="image/webp")
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("questoes_admin:admin_questao_criar"),
            data,
        )

        questao = Questao.objects.get(codigo="MAT-036-ALTIMG")
        alternativa = questao.alternativas.get(chave="B")
        self.assertRedirects(response, reverse("questoes_admin:admin_questao_detalhe", args=[questao.pk]))
        self.assertEqual(alternativa.texto, "")
        self.assertEqual(alternativa.imagem_public_id, "plataforma-estudos/alternativas/a")
        upload_mock.assert_called_once()

    def test_admin_edita_preserva_criado_por_e_slug_inexistente(self):
        questao = self.criar_questao("MAT-037")
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("questoes_admin:admin_questao_editar", args=[questao.pk]),
            self._post_questao(
                "MAT-037-EDIT",
                status=Questao.StatusQuestao.RASCUNHO,
                questao=questao,
            ),
        )

        questao.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("questoes_admin:admin_questao_detalhe", args=[questao.pk]),
        )
        self.assertEqual(questao.criado_por, self.staff)
        self.assertEqual(questao.codigo, "MAT-037-EDIT")

    def test_admin_publica_e_arquiva_por_post(self):
        questao = self.criar_questao("MAT-038", status=Questao.StatusQuestao.RASCUNHO)
        self.client.force_login(self.staff)

        get_response = self.client.get(
            reverse(
                "questoes_admin:admin_questao_alterar_status",
                args=[questao.pk, Questao.StatusQuestao.PUBLICADA],
            )
        )
        questao.refresh_from_db()
        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(questao.status, Questao.StatusQuestao.RASCUNHO)

        self.client.post(
            reverse(
                "questoes_admin:admin_questao_alterar_status",
                args=[questao.pk, Questao.StatusQuestao.PUBLICADA],
            )
        )
        questao.refresh_from_db()
        self.assertEqual(questao.status, Questao.StatusQuestao.PUBLICADA)

        self.client.post(
            reverse(
                "questoes_admin:admin_questao_alterar_status",
                args=[questao.pk, Questao.StatusQuestao.ARQUIVADA],
            )
        )
        questao.refresh_from_db()
        self.assertEqual(questao.status, Questao.StatusQuestao.ARQUIVADA)

    def test_admin_publica_todos_os_rascunhos_validos(self):
        valida = self.criar_questao(
            "MAT-038-LOTE",
            status=Questao.StatusQuestao.RASCUNHO,
        )
        invalida = Questao.objects.create(
            codigo="MAT-038-INVALIDA",
            materia=self.matematica,
            enunciado="Questão ainda sem alternativas.",
            status=Questao.StatusQuestao.RASCUNHO,
            criado_por=self.staff,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("questoes_admin:admin_questoes_publicar_rascunhos"),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        valida.refresh_from_db()
        invalida.refresh_from_db()
        self.assertEqual(valida.status, Questao.StatusQuestao.PUBLICADA)
        self.assertEqual(invalida.status, Questao.StatusQuestao.RASCUNHO)
        self.assertContains(response, "publicada(s) com sucesso")
        self.assertContains(response, "permaneceram em rascunho")

    def test_publicacao_em_lote_exige_post_e_usuario_staff(self):
        questao = self.criar_questao(
            "MAT-038-PERMISSAO",
            status=Questao.StatusQuestao.RASCUNHO,
        )
        url = reverse("questoes_admin:admin_questoes_publicar_rascunhos")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 405)

        self.client.force_login(self.estudante)
        self.assertEqual(self.client.post(url).status_code, 403)
        questao.refresh_from_db()
        self.assertEqual(questao.status, Questao.StatusQuestao.RASCUNHO)

    def test_admin_acessa_importacao_json_e_estudante_nao_acessa(self):
        url = reverse("questoes_admin:admin_questoes_importar_json")
        self.client.force_login(self.staff)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Importar questões por JSON")

        self.client.force_login(self.estudante)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"json_questoes": "{}"}).status_code, 403)

    def test_importacao_json_valida_cria_questao_alternativas_e_conteudos(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("questoes_admin:admin_questoes_importar_json"),
            {"json_questoes": json.dumps(self._payload_importacao("JSON-001"))},
            follow=True,
        )

        self.assertRedirects(response, reverse("questoes_admin:admin_questoes_lista"))
        questao = Questao.objects.get(codigo="JSON-001")
        self.assertEqual(questao.status, Questao.StatusQuestao.RASCUNHO)
        self.assertEqual(questao.materia, self.matematica)
        self.assertEqual(questao.alternativas.count(), 3)
        self.assertEqual(questao.alternativas.get(correta=True).chave, "C")
        self.assertEqual(questao.questao_conteudos.count(), 2)
        self.assertEqual(
            questao.questao_conteudos.get(principal=True).conteudo,
            self.conteudo,
        )

    def test_importacao_json_com_varias_questoes_cria_todas(self):
        self.client.force_login(self.staff)
        payload = self._payload_importacao("JSON-002")
        payload["questoes"].append(self._item_importacao("JSON-003"))

        response = self.client.post(
            reverse("questoes_admin:admin_questoes_importar_json"),
            {"json_questoes": json.dumps(payload)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Questao.objects.filter(codigo="JSON-002").exists())
        self.assertTrue(Questao.objects.filter(codigo="JSON-003").exists())

    def test_importacao_json_invalido_nao_cria_nada(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("questoes_admin:admin_questoes_importar_json"),
            {"json_questoes": "{"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Questao.objects.filter(codigo__startswith="JSON-").exists())
        self.assertContains(response, "O JSON informado é inválido")

    def test_importacao_json_segunda_questao_invalida_causa_rollback(self):
        self.client.force_login(self.staff)
        payload = self._payload_importacao("JSON-004")
        invalida = self._item_importacao("JSON-005")
        invalida["alternativas"] = []
        payload["questoes"].append(invalida)

        response = self.client.post(
            reverse("questoes_admin:admin_questoes_importar_json"),
            {"json_questoes": json.dumps(payload)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Questao.objects.filter(codigo="JSON-004").exists())
        self.assertFalse(Questao.objects.filter(codigo="JSON-005").exists())

    def test_importacao_json_rejeita_materia_e_conteudo_invalidos(self):
        casos = [
            ("JSON-006", {"materia": "matematica-avancada"}, "matéria"),
            ("JSON-007", {"conteudos": ["nao-existe"], "conteudo_principal": "nao-existe"}, "conteúdo"),
            (
                "JSON-008",
                {"conteudos": [self.conteudo_fisica.slug], "conteudo_principal": self.conteudo_fisica.slug},
                "não pertence",
            ),
        ]
        self.client.force_login(self.staff)
        for codigo, alteracoes, texto_erro in casos:
            payload = self._payload_importacao(codigo)
            payload["questoes"][0].update(alteracoes)
            response = self.client.post(
                reverse("questoes_admin:admin_questoes_importar_json"),
                {"json_questoes": json.dumps(payload)},
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, texto_erro)
            self.assertFalse(Questao.objects.filter(codigo=codigo).exists())

    def test_importacao_json_rejeita_alternativas_invalidas(self):
        casos = [
            ("JSON-009", [(0, False), (1, False), (2, False)], "nenhuma alternativa"),
            ("JSON-010", [(0, True), (1, True), (2, False)], "duas alternativas"),
        ]
        self.client.force_login(self.staff)
        for codigo, corretas, texto_erro in casos:
            payload = self._payload_importacao(codigo)
            for indice, correta in corretas:
                payload["questoes"][0]["alternativas"][indice]["correta"] = correta
            response = self.client.post(
                reverse("questoes_admin:admin_questoes_importar_json"),
                {"json_questoes": json.dumps(payload)},
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, texto_erro)
            self.assertFalse(Questao.objects.filter(codigo=codigo).exists())

    def test_importacao_json_rejeita_chaves_duplicadas_gabarito_divergente_e_imagem(self):
        casos = [
            ("JSON-011", {"alternativas": [{"chave": "A", "texto": "A", "correta": False, "ordem": 1}, {"chave": "A", "texto": "B", "correta": False, "ordem": 2}, {"chave": "C", "texto": "C", "correta": True, "ordem": 3}]}, "duplicada"),
            ("JSON-012", {"gabarito": "B"}, "diverge"),
            ("JSON-013", {"requer_imagem": True}, "requer imagem"),
        ]
        self.client.force_login(self.staff)
        for codigo, alteracoes, texto_erro in casos:
            payload = self._payload_importacao(codigo)
            payload["questoes"][0].update(alteracoes)
            response = self.client.post(
                reverse("questoes_admin:admin_questoes_importar_json"),
                {"json_questoes": json.dumps(payload)},
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, texto_erro)
            self.assertFalse(Questao.objects.filter(codigo=codigo).exists())

    def test_importacao_json_rejeita_codigo_duplicado(self):
        self.criar_questao("JSON-014")
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("questoes_admin:admin_questoes_importar_json"),
            {"json_questoes": json.dumps(self._payload_importacao("JSON-014"))},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Questão JSON-014 já existe.")

    def test_importacao_json_respeita_status_publicado_quando_valido(self):
        self.client.force_login(self.staff)
        payload = self._payload_importacao("JSON-015")
        payload["questoes"][0]["status"] = Questao.StatusQuestao.PUBLICADA
        response = self.client.post(
            reverse("questoes_admin:admin_questoes_importar_json"),
            {"json_questoes": json.dumps(payload)},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Questao.objects.get(codigo="JSON-015").status,
            Questao.StatusQuestao.PUBLICADA,
        )

    @patch("questoes.importacao_json.validar_public_id")
    def test_importacao_json_aceita_imagem_null_ausente_e_public_id(self, validar_mock):
        self.client.force_login(self.staff)
        payload = self._payload_importacao("JSON-016")
        payload["questoes"][0]["imagem"] = {
            "public_id": "enem/2025/caderno7/q136",
            "alt": "Gráfico da questão",
        }
        payload["questoes"][0]["alternativas"][0]["imagem"] = None
        payload["questoes"][0]["alternativas"][1]["imagem"] = {
            "public_id": "enem/2025/caderno7/q136-b",
            "alt": "Figura da alternativa B",
        }
        payload["questoes"][0]["alternativas"][1]["texto"] = ""

        response = self.client.post(
            reverse("questoes_admin:admin_questoes_importar_json"),
            {"json_questoes": json.dumps(payload)},
        )

        questao = Questao.objects.get(codigo="JSON-016")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(questao.imagem_public_id, "enem/2025/caderno7/q136")
        self.assertEqual(questao.imagem_alt, "Gráfico da questão")
        self.assertEqual(
            questao.alternativas.get(chave="B").imagem_public_id,
            "enem/2025/caderno7/q136-b",
        )
        self.assertEqual(validar_mock.call_count, 2)

    @patch("questoes.importacao_json.validar_public_id")
    def test_importacao_json_preserva_public_id_simples_sem_extensao_e_requer_imagem(self, validar_mock):
        self.client.force_login(self.staff)
        payload = self._payload_importacao("JSON-016-SIMPLES")
        payload["questoes"][0]["requer_imagem"] = True
        payload["questoes"][0]["imagem"] = {"public_id": "abc123", "alt": "Imagem simples"}

        response = self.client.post(
            reverse("questoes_admin:admin_questoes_importar_json"),
            {"json_questoes": json.dumps(payload)},
        )

        questao = Questao.objects.get(codigo="JSON-016-SIMPLES")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(questao.imagem_public_id, "abc123")
        self.assertNotEqual(questao.imagem_public_id, "abc123.png")
        validar_mock.assert_called_once_with("abc123")

    @patch("questoes.importacao_json.validar_public_id", side_effect=ValidationError('Imagem Cloudinary "nao-existe" não encontrada.'))
    def test_importacao_json_public_id_inexistente_faz_rollback(self, validar_mock):
        self.client.force_login(self.staff)
        payload = self._payload_importacao("JSON-017")
        payload["questoes"][0]["imagem"] = {"public_id": "nao-existe", "alt": ""}

        response = self.client.post(
            reverse("questoes_admin:admin_questoes_importar_json"),
            {"json_questoes": json.dumps(payload)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Imagem Cloudinary &quot;nao-existe&quot; não encontrada.')
        self.assertFalse(Questao.objects.filter(codigo="JSON-017").exists())
        validar_mock.assert_called_once_with("nao-existe")

    def test_admin_busca_e_filtros(self):
        publicada = self.criar_questao("MAT-039", dificuldade=Questao.DificuldadeQuestao.FACIL)
        arquivada = self.criar_questao(
            "MAT-040",
            status=Questao.StatusQuestao.ARQUIVADA,
            dificuldade=Questao.DificuldadeQuestao.DIFICIL,
            conteudos=[self.outro_conteudo],
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("questoes_admin:admin_questoes_lista"), {"q": "039"})
        self.assertContains(response, publicada.codigo)
        self.assertNotContains(response, arquivada.codigo)

        response = self.client.get(
            reverse("questoes_admin:admin_questoes_lista"),
            {
                "materia": self.matematica.slug,
                "conteudo": str(self.outro_conteudo.pk),
                "dificuldade": Questao.DificuldadeQuestao.DIFICIL,
                "status": Questao.StatusQuestao.ARQUIVADA,
            },
        )
        self.assertContains(response, arquivada.codigo)
        self.assertNotContains(response, publicada.codigo)

    def test_admin_visualiza_respostas_sem_editar(self):
        questao = self.criar_questao("MAT-041")
        resposta = RespostaQuestao.objects.create(
            usuario=self.estudante,
            questao=questao,
            alternativa_escolhida=self.alternativa(questao, correta=True),
            correta=False,
        )
        self.client.force_login(self.staff)
        lista = self.client.get(reverse("questoes_admin:admin_respostas_lista"), {"resultado": "acertos"})
        self.assertContains(lista, questao.codigo)
        detalhe = self.client.get(reverse("questoes_admin:admin_resposta_detalhe", args=[resposta.pk]))
        self.assertContains(detalhe, self.estudante.email)

    def _post_questao(self, codigo, status, questao=None):
        alternativas = list(questao.alternativas.order_by("ordem")) if questao else []
        data = {
            "codigo": codigo,
            "materia": str(self.matematica.pk),
            "enunciado": f"Enunciado {codigo}",
            "explicacao": "Explicação administrativa",
            "dificuldade": Questao.DificuldadeQuestao.MEDIA,
            "tipo_fonte": Questao.TipoFonte.ORIGINAL,
            "fonte_nome": "",
            "fonte_ano": "",
            "fonte_url": "",
            "status": status,
            "conteudos": [str(self.conteudo.pk)],
            "conteudo_principal": str(self.conteudo.pk),
            "alternativas-TOTAL_FORMS": "5",
            "alternativas-INITIAL_FORMS": str(len(alternativas)),
            "alternativas-MIN_NUM_FORMS": "0",
            "alternativas-MAX_NUM_FORMS": "1000",
            "alternativas-0-chave": "A",
            "alternativas-0-texto": "Correta",
            "alternativas-0-correta": "on",
            "alternativas-0-ordem": "1",
            "alternativas-1-chave": "B",
            "alternativas-1-texto": "Incorreta",
            "alternativas-1-ordem": "2",
            "alternativas-2-chave": "",
            "alternativas-2-texto": "",
            "alternativas-2-ordem": "",
            "alternativas-3-chave": "",
            "alternativas-3-texto": "",
            "alternativas-3-ordem": "",
            "alternativas-4-chave": "",
            "alternativas-4-texto": "",
            "alternativas-4-ordem": "",
        }
        for indice, alternativa in enumerate(alternativas):
            data[f"alternativas-{indice}-id"] = str(alternativa.pk)
        return data

    def _payload_importacao(self, codigo):
        return {"materia": self.matematica.slug, "questoes": [self._item_importacao(codigo)]}

    def _item_importacao(self, codigo):
        return {
            "codigo": codigo,
            "ano": 2024,
            "caderno": "7 - Azul",
            "numero_questao": 140,
            "enunciado": f"Enunciado importado {codigo}",
            "explicacao": "Explicação importada",
            "dificuldade": Questao.DificuldadeQuestao.MEDIA,
            "tipo_fonte": Questao.TipoFonte.ENEM,
            "fonte_nome": "ENEM",
            "fonte_ano": 2024,
            "fonte_url": "https://example.com",
            "status": Questao.StatusQuestao.RASCUNHO,
            "conteudo_principal": self.conteudo.slug,
            "conteudos": [self.conteudo.slug, self.outro_conteudo.slug],
            "gabarito": "C",
            "requer_imagem": False,
            "observacao_revisao": "Ignorado pela importação.",
            "alternativas": [
                {"chave": "A", "texto": "Alternativa A", "correta": False, "ordem": 1},
                {"chave": "B", "texto": "Alternativa B", "correta": False, "ordem": 2},
                {"chave": "C", "texto": "Alternativa C", "correta": True, "ordem": 3},
            ],
        }
