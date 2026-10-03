import io
import json
import socket
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import F
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from curriculo.models import Conteudo, Materia
from estudos.models import ConteudoEstudado

from .importacao_json import importar_videos_json
from .models import ProgressoVideo, SessaoVideo, VideoConteudo
from .templatetags.videos_extras import segundos_mmss
from .youtube import buscar_metadados_youtube, extrair_youtube_id


Usuario = get_user_model()

YOUTUBE_ID = "dQw4w9WgXcQ"
OUTRO_ID = "abcdefghijk"
PATCH_OEMBED = "videos.youtube.buscar_metadados_youtube"


def metadados_falsos(youtube_id):
    return {
        "titulo": f"Aula oficial {youtube_id}",
        "canal_nome": "Canal Oficial",
        "canal_url": "https://www.youtube.com/@canaloficial",
        "thumbnail_url": f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg",
    }


class VideosTestMixin:
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
            slug="porcentagem",
            resumo="Resumo de porcentagem",
            status=Conteudo.StatusConteudo.PUBLICADO,
            criado_por=self.staff,
        )
        self.conteudo_fisica = Conteudo.objects.create(
            materia=self.fisica,
            titulo="Cinemática",
            slug="cinematica",
            resumo="Resumo de cinemática",
            status=Conteudo.StatusConteudo.PUBLICADO,
            criado_por=self.staff,
        )

    def criar_video(self, youtube_id=YOUTUBE_ID, conteudo=None, ativo=True, duracao=None, **extra):
        return VideoConteudo.objects.create(
            conteudo=conteudo or self.conteudo,
            youtube_id=youtube_id,
            titulo=f"Aula {youtube_id}",
            canal_nome="Canal Oficial",
            canal_url="https://www.youtube.com/@canaloficial",
            ativo=ativo,
            duracao_segundos=duracao,
            criado_por=self.staff,
            **extra,
        )


class ExtrairYoutubeIdTests(SimpleTestCase):
    def test_formatos_aceitos(self):
        links = [
            f"https://www.youtube.com/watch?v={YOUTUBE_ID}",
            f"https://youtube.com/watch?v={YOUTUBE_ID}&t=42s&list=PL123",
            f"https://m.youtube.com/watch?v={YOUTUBE_ID}",
            f"www.youtube.com/watch?v={YOUTUBE_ID}",
            f"https://youtu.be/{YOUTUBE_ID}",
            f"https://youtu.be/{YOUTUBE_ID}?t=10",
            f"https://www.youtube.com/shorts/{YOUTUBE_ID}",
            f"https://www.youtube.com/embed/{YOUTUBE_ID}",
            f"https://www.youtube.com/live/{YOUTUBE_ID}",
            f"https://www.youtube-nocookie.com/embed/{YOUTUBE_ID}",
            YOUTUBE_ID,
            f"  {YOUTUBE_ID}  ",
        ]
        for link in links:
            with self.subTest(link=link):
                self.assertEqual(extrair_youtube_id(link), YOUTUBE_ID)

    def test_links_invalidos(self):
        links = [
            "",
            f"https://vimeo.com/watch?v={YOUTUBE_ID}",
            f"https://youtube.com.evil.com/watch?v={YOUTUBE_ID}",
            "https://www.youtube.com/watch?v=curto",
            f"https://www.youtube.com/watch?v={YOUTUBE_ID}X",
            "https://www.youtube.com/channel/UC123",
            f"https://youtu.be/{YOUTUBE_ID}/extra",
            f"javascript:alert('{YOUTUBE_ID}')",
            "abc$efghijk",
        ]
        for link in links:
            with self.subTest(link=link):
                with self.assertRaisesMessage(ValidationError, "Link do YouTube inválido."):
                    extrair_youtube_id(link)


class SegundosMmssTests(SimpleTestCase):
    def test_formatos(self):
        self.assertEqual(segundos_mmss(0), "00:00")
        self.assertEqual(segundos_mmss(75), "01:15")
        self.assertEqual(segundos_mmss(3599), "59:59")
        self.assertEqual(segundos_mmss(3725), "1:02:05")
        self.assertEqual(segundos_mmss(None), "00:00")


class BuscarMetadadosTests(SimpleTestCase):
    def resposta(self, dados):
        return io.BytesIO(json.dumps(dados).encode("utf-8"))

    def erro_http(self, codigo):
        return HTTPError("https://www.youtube.com/oembed", codigo, "erro", {}, None)

    @patch("videos.youtube.urlopen")
    def test_sucesso_e_thumbnail_padrao(self, urlopen):
        urlopen.return_value = self.resposta(
            {"title": "Aula", "author_name": "Canal", "author_url": "https://www.youtube.com/@canal"}
        )
        dados = buscar_metadados_youtube(YOUTUBE_ID)
        self.assertEqual(dados["titulo"], "Aula")
        self.assertEqual(dados["canal_nome"], "Canal")
        self.assertEqual(dados["thumbnail_url"], f"https://i.ytimg.com/vi/{YOUTUBE_ID}/hqdefault.jpg")
        requisicao = urlopen.call_args.args[0]
        self.assertIn("youtube.com%2Fwatch%3Fv%3D" + YOUTUBE_ID, requisicao.full_url)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)

    @patch("videos.youtube.urlopen")
    def test_privado_ou_sem_incorporacao(self, urlopen):
        for codigo in (401, 403):
            urlopen.side_effect = self.erro_http(codigo)
            with self.assertRaisesMessage(ValidationError, "O vídeo é privado"):
                buscar_metadados_youtube(YOUTUBE_ID)

    @patch("videos.youtube.urlopen")
    def test_nao_encontrado(self, urlopen):
        for codigo in (400, 404):
            urlopen.side_effect = self.erro_http(codigo)
            with self.assertRaisesMessage(ValidationError, "Vídeo não encontrado"):
                buscar_metadados_youtube(YOUTUBE_ID)

    @patch("videos.youtube.urlopen")
    def test_timeout_e_erro_de_rede(self, urlopen):
        for erro in (socket.timeout("timed out"), TimeoutError(), URLError("sem rede")):
            urlopen.side_effect = erro
            with self.assertRaisesMessage(ValidationError, "Não foi possível consultar o YouTube agora"):
                buscar_metadados_youtube(YOUTUBE_ID)

    @patch("videos.youtube.urlopen")
    def test_resposta_sem_autoria(self, urlopen):
        urlopen.return_value = self.resposta({"title": "Aula"})
        with self.assertRaisesMessage(ValidationError, "O YouTube não retornou os dados de autoria do vídeo."):
            buscar_metadados_youtube(YOUTUBE_ID)


@patch(PATCH_OEMBED, side_effect=metadados_falsos)
class AdminVideoTests(VideosTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def dados_criar(self, **extra):
        dados = {
            "conteudo": self.conteudo.pk,
            "url": f"https://youtu.be/{YOUTUBE_ID}",
            "nota_curador": "Explicação clara.",
            "ordem": 1,
            "ativo": "on",
        }
        dados.update(extra)
        return dados

    def test_criar_grava_autoria_do_youtube_e_nao_do_post(self, oembed):
        response = self.client.post(
            reverse("videos_admin:criar"),
            self.dados_criar(titulo="Título falso", canal_nome="Canal falso", canal_url="https://evil.com"),
        )
        video = VideoConteudo.objects.get()
        self.assertRedirects(response, reverse("videos_admin:detalhe", args=[video.pk]))
        self.assertEqual(video.youtube_id, YOUTUBE_ID)
        self.assertEqual(video.titulo, f"Aula oficial {YOUTUBE_ID}")
        self.assertEqual(video.canal_nome, "Canal Oficial")
        self.assertEqual(video.canal_url, "https://www.youtube.com/@canaloficial")
        self.assertEqual(video.criado_por, self.staff)
        self.assertIsNotNone(video.metadados_atualizados_em)
        oembed.assert_called_once_with(YOUTUBE_ID)

    def test_criar_recusa_duplicado_no_mesmo_conteudo(self, oembed):
        self.criar_video()
        response = self.client.post(reverse("videos_admin:criar"), self.dados_criar())
        self.assertContains(response, "Este vídeo já está cadastrado neste conteúdo.")
        self.assertEqual(VideoConteudo.objects.count(), 1)

    def test_mesmo_video_em_outro_conteudo_e_permitido(self, oembed):
        self.criar_video()
        self.client.post(reverse("videos_admin:criar"), self.dados_criar(conteudo=self.conteudo_fisica.pk))
        self.assertEqual(VideoConteudo.objects.count(), 2)

    def test_criar_mostra_erro_do_youtube_sem_gravar(self, oembed):
        oembed.side_effect = ValidationError("O vídeo é privado ou o autor não permite incorporá-lo em outros sites.")
        response = self.client.post(reverse("videos_admin:criar"), self.dados_criar())
        self.assertContains(response, "O vídeo é privado")
        self.assertFalse(VideoConteudo.objects.exists())

    def test_criar_com_link_invalido(self, oembed):
        response = self.client.post(reverse("videos_admin:criar"), self.dados_criar(url="https://vimeo.com/123"))
        self.assertContains(response, "Link do YouTube inválido.")
        oembed.assert_not_called()

    def test_criar_pre_seleciona_conteudo(self, oembed):
        response = self.client.get(reverse("videos_admin:criar") + f"?conteudo={self.conteudo.pk}")
        self.assertEqual(response.context["form"].initial["conteudo"], self.conteudo)
        response = self.client.get(reverse("videos_admin:criar") + "?conteudo=lixo")
        self.assertEqual(response.status_code, 200)

    def test_editar_nao_altera_autoria(self, oembed):
        video = self.criar_video()
        response = self.client.post(
            reverse("videos_admin:editar", args=[video.pk]),
            {
                "conteudo": self.conteudo.pk,
                "nota_curador": "Nova nota",
                "ordem": 3,
                "titulo": "Título falso",
                "canal_nome": "Canal falso",
                "youtube_id": OUTRO_ID,
            },
        )
        self.assertRedirects(response, reverse("videos_admin:detalhe", args=[video.pk]))
        video.refresh_from_db()
        self.assertEqual(video.nota_curador, "Nova nota")
        self.assertEqual(video.ordem, 3)
        self.assertFalse(video.ativo)
        self.assertEqual(video.titulo, f"Aula {YOUTUBE_ID}")
        self.assertEqual(video.canal_nome, "Canal Oficial")
        self.assertEqual(video.youtube_id, YOUTUBE_ID)
        oembed.assert_not_called()

    def test_editar_para_conteudo_com_mesmo_video_e_recusado(self, oembed):
        self.criar_video(conteudo=self.conteudo_fisica)
        video = self.criar_video()
        response = self.client.post(
            reverse("videos_admin:editar", args=[video.pk]),
            {"conteudo": self.conteudo_fisica.pk, "ordem": 0, "ativo": "on"},
        )
        self.assertContains(response, "Este vídeo já está cadastrado neste conteúdo.")

    def test_alternar_status_somente_por_post(self, oembed):
        video = self.criar_video()
        url = reverse("videos_admin:alternar_status", args=[video.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        video.refresh_from_db()
        self.assertTrue(video.ativo)
        self.client.post(url)
        video.refresh_from_db()
        self.assertFalse(video.ativo)
        self.client.post(url)
        video.refresh_from_db()
        self.assertTrue(video.ativo)

    def test_atualizar_dados_do_youtube(self, oembed):
        video = self.criar_video()
        self.client.post(reverse("videos_admin:atualizar_dados", args=[video.pk]))
        video.refresh_from_db()
        self.assertEqual(video.titulo, f"Aula oficial {YOUTUBE_ID}")

    def test_atualizar_dados_com_falha_nao_desativa(self, oembed):
        oembed.side_effect = ValidationError("Vídeo não encontrado. Ele pode ter sido removido ou o link está incorreto.")
        video = self.criar_video()
        response = self.client.post(reverse("videos_admin:atualizar_dados", args=[video.pk]), follow=True)
        self.assertContains(response, "considere desativá-lo")
        video.refresh_from_db()
        self.assertTrue(video.ativo)
        self.assertEqual(video.titulo, f"Aula {YOUTUBE_ID}")

    def test_preview(self, oembed):
        response = self.client.get(reverse("videos_admin:preview") + f"?url=https://youtu.be/{YOUTUBE_ID}")
        self.assertEqual(response.json()["ok"], True)
        self.assertEqual(response.json()["canal_nome"], "Canal Oficial")
        response = self.client.get(reverse("videos_admin:preview") + "?url=https://vimeo.com/1")
        self.assertEqual(response.json(), {"ok": False, "erro": "Link do YouTube inválido."})

    def test_lista_filtros_e_detalhe(self, oembed):
        video = self.criar_video()
        self.criar_video(OUTRO_ID, conteudo=self.conteudo_fisica, ativo=False)
        ProgressoVideo.objects.create(usuario=self.usuario, video=video, concluido=True)
        ProgressoVideo.objects.create(usuario=self.outro_usuario, video=video)

        lista = self.client.get(reverse("videos_admin:lista") + "?materia=fisica&status=inativos")
        self.assertEqual([item.youtube_id for item in lista.context["page_obj"]], [OUTRO_ID])
        busca = self.client.get(reverse("videos_admin:lista") + "?q=porcent")
        self.assertEqual([item.youtube_id for item in busca.context["page_obj"]], [YOUTUBE_ID])

        detalhe = self.client.get(reverse("videos_admin:detalhe", args=[video.pk]))
        self.assertEqual((detalhe.context["iniciaram"], detalhe.context["concluiram"]), (2, 1))
        self.assertContains(detalhe, 'referrerpolicy="strict-origin-when-cross-origin"')

    def test_conteudo_admin_lista_videos(self, oembed):
        self.criar_video()
        response = self.client.get(reverse("curriculo_admin:admin_conteudo_detalhe", args=[self.conteudo.pk]))
        self.assertContains(response, "Vídeos deste conteúdo")
        self.assertContains(response, f"Aula {YOUTUBE_ID}")
        self.assertContains(response, reverse("videos_admin:criar") + f"?conteudo={self.conteudo.pk}")

    def test_estudante_recebe_403_nas_rotas_admin(self, oembed):
        video = self.criar_video()
        self.client.force_login(self.usuario)
        rotas = [
            ("get", reverse("videos_admin:lista")),
            ("get", reverse("videos_admin:criar")),
            ("get", reverse("videos_admin:preview") + f"?url={YOUTUBE_ID}"),
            ("get", reverse("videos_admin:importar_json")),
            ("get", reverse("videos_admin:detalhe", args=[video.pk])),
            ("get", reverse("videos_admin:editar", args=[video.pk])),
            ("post", reverse("videos_admin:alternar_status", args=[video.pk])),
            ("post", reverse("videos_admin:atualizar_dados", args=[video.pk])),
        ]
        for metodo, url in rotas:
            with self.subTest(url=url):
                self.assertEqual(getattr(self.client, metodo)(url).status_code, 403)
        video.refresh_from_db()
        self.assertTrue(video.ativo)
        oembed.assert_not_called()


@patch(PATCH_OEMBED, side_effect=metadados_falsos)
class ImportacaoJsonVideosTests(VideosTestMixin, TestCase):
    def json_videos(self, videos, **topo):
        return json.dumps({**topo, "videos": videos})

    def test_importa_com_materia_padrao(self, oembed):
        texto = self.json_videos(
            [
                {"conteudo": "porcentagem", "url": f"https://youtu.be/{YOUTUBE_ID}", "nota_curador": "Boa aula", "ordem": 2},
                {"conteudo": "porcentagem", "youtube_id": OUTRO_ID, "ativo": False},
                {"materia": "fisica", "conteudo": "cinematica", "url": f"https://www.youtube.com/watch?v={YOUTUBE_ID}"},
            ],
            materia="matematica",
        )
        videos = importar_videos_json(texto, self.staff)
        self.assertEqual(len(videos), 3)
        self.assertEqual(VideoConteudo.objects.count(), 3)
        video = VideoConteudo.objects.get(conteudo=self.conteudo, youtube_id=YOUTUBE_ID)
        self.assertEqual((video.nota_curador, video.ordem, video.ativo), ("Boa aula", 2, True))
        self.assertEqual(video.criado_por, self.staff)
        self.assertFalse(VideoConteudo.objects.get(youtube_id=OUTRO_ID).ativo)
        # Um único acesso ao oEmbed por vídeo, mesmo repetido em conteúdos diferentes.
        self.assertEqual(oembed.call_count, 2)

    def test_campos_de_autoria_no_json_sao_ignorados(self, oembed):
        texto = self.json_videos(
            [{
                "materia": "matematica",
                "conteudo": "porcentagem",
                "youtube_id": YOUTUBE_ID,
                "titulo": "Falso",
                "canal": "Falso",
                "canal_nome": "Falso",
                "canal_url": "https://evil.com",
            }]
        )
        importar_videos_json(texto, self.staff)
        video = VideoConteudo.objects.get()
        self.assertEqual(video.titulo, f"Aula oficial {YOUTUBE_ID}")
        self.assertEqual(video.canal_url, "https://www.youtube.com/@canaloficial")

    def test_materia_e_conteudo_inexistentes(self, oembed):
        texto = self.json_videos(
            [
                {"materia": "quimica", "conteudo": "porcentagem", "youtube_id": YOUTUBE_ID},
                {"materia": "matematica", "conteudo": "inexistente", "youtube_id": YOUTUBE_ID},
                {"materia": "matematica", "conteudo": "cinematica", "youtube_id": YOUTUBE_ID},
                {"materia": "matematica", "conteudo": "porcentagem"},
            ]
        )
        with self.assertRaises(ValidationError) as contexto:
            importar_videos_json(texto, self.staff)
        mensagens = contexto.exception.messages
        self.assertIn('Vídeo 1: matéria "quimica" não encontrada.', mensagens)
        self.assertIn('Vídeo 2: conteúdo "inexistente" não encontrado.', mensagens)
        self.assertIn('Vídeo 3: conteúdo "cinematica" não pertence à matéria "matematica".', mensagens)
        self.assertIn("Vídeo 4: informe url ou youtube_id.", mensagens)
        oembed.assert_not_called()
        self.assertFalse(VideoConteudo.objects.exists())

    def test_duplicado_no_json_e_no_banco(self, oembed):
        self.criar_video(OUTRO_ID)
        texto = self.json_videos(
            [
                {"conteudo": "porcentagem", "youtube_id": YOUTUBE_ID},
                {"conteudo": "porcentagem", "url": f"https://youtu.be/{YOUTUBE_ID}"},
                {"conteudo": "porcentagem", "youtube_id": OUTRO_ID},
            ],
            materia="matematica",
        )
        with self.assertRaises(ValidationError) as contexto:
            importar_videos_json(texto, self.staff)
        mensagens = " ".join(contexto.exception.messages)
        self.assertIn("Vídeo 2: o vídeo", mensagens)
        self.assertIn("repetido", mensagens)
        self.assertIn("Vídeo 3: o vídeo", mensagens)
        self.assertIn("já está cadastrado", mensagens)
        self.assertEqual(VideoConteudo.objects.count(), 1)

    def test_falha_no_youtube_cancela_tudo(self, oembed):
        def oembed_com_falha(youtube_id):
            if youtube_id == OUTRO_ID:
                raise ValidationError("O vídeo é privado ou o autor não permite incorporá-lo em outros sites.")
            return metadados_falsos(youtube_id)

        oembed.side_effect = oembed_com_falha
        texto = self.json_videos(
            [
                {"conteudo": "porcentagem", "youtube_id": YOUTUBE_ID},
                {"conteudo": "porcentagem", "youtube_id": OUTRO_ID},
            ],
            materia="matematica",
        )
        with self.assertRaises(ValidationError) as contexto:
            importar_videos_json(texto, self.staff)
        self.assertEqual(
            contexto.exception.messages,
            ["Vídeo 2: O vídeo é privado ou o autor não permite incorporá-lo em outros sites."],
        )
        self.assertFalse(VideoConteudo.objects.exists())

    def test_limite_de_50_itens(self, oembed):
        itens = [{"conteudo": "porcentagem", "youtube_id": f"video{indice:06d}"} for indice in range(51)]
        with self.assertRaisesMessage(ValidationError, "no máximo 50 itens"):
            importar_videos_json(self.json_videos(itens, materia="matematica"), self.staff)
        oembed.assert_not_called()

    def test_campos_invalidos_e_json_vazio(self, oembed):
        with self.assertRaisesMessage(ValidationError, 'Campo "videos" não pode ser vazio.'):
            importar_videos_json(self.json_videos([]), self.staff)
        with self.assertRaisesMessage(ValidationError, "O JSON informado é inválido."):
            importar_videos_json("{", self.staff)
        texto = self.json_videos(
            [{"conteudo": "porcentagem", "youtube_id": YOUTUBE_ID, "ordem": -1, "ativo": "sim", "nota_curador": 3}],
            materia="matematica",
        )
        with self.assertRaises(ValidationError) as contexto:
            importar_videos_json(texto, self.staff)
        self.assertEqual(len(contexto.exception.messages), 3)

    def test_tela_de_importacao(self, oembed):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("videos_admin:importar_json"))
        self.assertContains(response, reverse("curriculo_admin:admin_padroes_importacao_json") + "?origem=videos")
        response = self.client.post(
            reverse("videos_admin:importar_json"),
            {"json_videos": self.json_videos([{"conteudo": "porcentagem", "youtube_id": YOUTUBE_ID}], materia="matematica")},
            follow=True,
        )
        self.assertContains(response, "Importação concluída. 1 vídeo(s) cadastrado(s) com sucesso.")


class PaginaConteudoVideosTests(VideosTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)
        self.url = reverse("curriculo:conteudo_detalhe", args=["matematica", "porcentagem"])

    def test_sem_videos_mostra_placeholder(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Materiais de estudo serão disponibilizados futuramente neste espaço.")
        self.assertNotContains(response, "youtube-nocookie.com")

    def test_video_ativo_mostra_player_com_autoria(self):
        video = self.criar_video(nota_curador="Veja antes das questões.")
        response = self.client.get(self.url)
        self.assertNotContains(response, "Materiais de estudo serão disponibilizados futuramente")
        self.assertContains(response, f'src="https://www.youtube-nocookie.com/embed/{YOUTUBE_ID}?enablejsapi=1')
        self.assertContains(response, 'referrerpolicy="strict-origin-when-cross-origin"')
        self.assertContains(response, f'id="video-{video.pk}"')
        self.assertContains(response, "Canal Oficial")
        self.assertContains(response, f'href="https://www.youtube.com/watch?v={YOUTUBE_ID}"')
        self.assertContains(response, "Assistir no YouTube")
        self.assertContains(response, "Nota do curador")
        self.assertContains(response, reverse("videos:registrar_progresso", args=[video.pk]))
        self.assertNotContains(response, "controls=0")
        self.assertNotContains(response, "origin=")
        self.assertContains(response, f'data-estudado-conteudo="{self.conteudo.pk}"')

    def test_video_inativo_nao_aparece(self):
        self.criar_video(ativo=False)
        response = self.client.get(self.url)
        self.assertNotContains(response, "youtube-nocookie.com")
        self.assertContains(response, "Materiais de estudo serão disponibilizados futuramente neste espaço.")

    def test_player_retoma_de_onde_parou(self):
        video = self.criar_video(duracao=600)
        ProgressoVideo.objects.create(usuario=self.usuario, video=video, ultima_posicao_segundos=125)
        response = self.client.get(self.url)
        self.assertContains(response, "&amp;start=125")
        self.assertContains(response, "Você parou em <span>02:05</span>")

    def test_player_nao_retoma_no_fim_nem_quando_concluido(self):
        video = self.criar_video(duracao=600)
        progresso = ProgressoVideo.objects.create(usuario=self.usuario, video=video, ultima_posicao_segundos=595)
        self.assertNotContains(self.client.get(self.url), "start=")
        progresso.ultima_posicao_segundos = 100
        progresso.concluido = True
        progresso.save()
        self.assertNotContains(self.client.get(self.url), "start=")

    def test_progresso_de_outro_aluno_nao_aparece(self):
        video = self.criar_video(duracao=600)
        ProgressoVideo.objects.create(usuario=self.outro_usuario, video=video, ultima_posicao_segundos=125, percentual=50)
        response = self.client.get(self.url)
        self.assertNotContains(response, "start=")
        self.assertNotContains(response, "Você parou em <span>02:05</span>")

    def test_consultas_sem_n_mais_1(self):
        for indice in range(5):
            video = self.criar_video(f"video{indice:06d}", duracao=300)
            ProgressoVideo.objects.create(usuario=self.usuario, video=video, ultima_posicao_segundos=60)
        from videos.services import videos_do_conteudo_para_usuario

        with self.assertNumQueries(2):
            itens = videos_do_conteudo_para_usuario(self.conteudo, self.usuario)
        self.assertEqual(len(itens), 5)
        self.assertTrue(all(item["progresso"] for item in itens))


class ProgressoVideoEndpointTests(VideosTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.video = self.criar_video()
        self.url = reverse("videos:registrar_progresso", args=[self.video.pk])
        self.sessao_id = str(uuid.uuid4())
        self.client.force_login(self.usuario)

    def enviar(self, cliente=None, url=None, **dados):
        corpo = {
            "sessao_id": self.sessao_id,
            "segmentos": [0, 1, 2],
            "posicao": 15,
            "duracao": 100,
            "segundos_assistidos": 15,
        }
        corpo.update(dados)
        return (cliente or self.client).post(url or self.url, json.dumps(corpo), content_type="application/json")

    def iniciar(self, cliente=None, **dados):
        """Aviso de início de reprodução enviado pelo player (sem blocos)."""
        return self.enviar(cliente=cliente, segmentos=[], posicao=0, segundos_assistidos=0, **dados)

    def passar_tempo(self, segundos, usuario=None):
        ProgressoVideo.objects.filter(usuario=usuario or self.usuario, video=self.video).update(
            atualizado_em=F("atualizado_em") - timedelta(seconds=segundos)
        )

    def assistir(self, blocos, cliente=None, usuario=None, **dados):
        """Simula reprodução real: lotes de até 10 blocos, com 30 s de relógio entre eles."""
        resposta = None
        for inicio in range(0, len(blocos), 10):
            lote = blocos[inicio:inicio + 10]
            self.passar_tempo(30, usuario=usuario)
            resposta = self.enviar(
                cliente=cliente,
                segmentos=lote,
                posicao=(lote[-1] + 1) * 5,
                segundos_assistidos=len(lote) * 5,
                **dados,
            )
        return resposta

    def test_sem_login_responde_401_em_json(self):
        self.client.logout()
        response = self.enviar()
        self.assertEqual(response.status_code, 401)
        self.assertIn("erro", response.json())

    def test_somente_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_video_inativo_ou_conteudo_nao_publicado_responde_404(self):
        self.video.ativo = False
        self.video.save()
        self.assertEqual(self.enviar().status_code, 404)
        self.video.ativo = True
        self.video.save()
        self.conteudo.status = Conteudo.StatusConteudo.RASCUNHO
        self.conteudo.save(update_fields=["status"])
        self.assertEqual(self.enviar().status_code, 404)
        self.conteudo.status = Conteudo.StatusConteudo.PUBLICADO
        self.conteudo.save(update_fields=["status"])
        self.matematica.ativa = False
        self.matematica.save(update_fields=["ativa"])
        self.assertEqual(self.enviar().status_code, 404)

    def test_json_e_campos_invalidos_respondem_400(self):
        self.assertEqual(self.client.post(self.url, "{nao-json", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(self.url, "x" * (21 * 1024), content_type="application/json").status_code, 400)
        invalidos = [
            {"sessao_id": "nao-e-uuid"},
            {"segmentos": "0,1"},
            {"segmentos": [0, "1"]},
            {"segmentos": [True]},
            {"segmentos": list(range(2001))},
            {"posicao": -1},
            {"duracao": 0},
            {"duracao": 21601},
            {"segundos_assistidos": "muito"},
        ]
        for dados in invalidos:
            with self.subTest(dados=dados):
                self.assertEqual(self.enviar(**dados).status_code, 400)
        self.assertFalse(ProgressoVideo.objects.exists())
        self.assertFalse(SessaoVideo.objects.exists())

    def test_sessao_de_outro_usuario_responde_400(self):
        self.assertEqual(self.enviar().status_code, 200)
        self.client.force_login(self.outro_usuario)
        response = self.enviar(segmentos=[3])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProgressoVideo.objects.filter(usuario=self.outro_usuario).exists())

    def test_sessao_de_outro_video_responde_400(self):
        outro_video = self.criar_video(OUTRO_ID)
        self.assertEqual(self.enviar().status_code, 200)
        url = reverse("videos:registrar_progresso", args=[outro_video.pk])
        self.assertEqual(self.enviar(url=url).status_code, 400)

    def test_aviso_de_inicio_cria_progresso_e_sessao_zerados(self):
        response = self.iniciar()
        self.assertEqual(response.json()["percentual"], 0.0)
        progresso = ProgressoVideo.objects.get()
        self.assertEqual((progresso.segmentos_assistidos, progresso.segundos_assistidos_total), ([], 0))
        self.assertEqual(SessaoVideo.objects.get().segundos_assistidos, 0)

    def test_uniao_de_blocos_entre_requisicoes_e_sessao(self):
        self.iniciar()
        self.passar_tempo(15)
        response = self.enviar(segmentos=[0, 1, 2], posicao=15, segundos_assistidos=15)
        self.assertEqual(
            response.json(),
            {"percentual": 15.0, "concluido": False, "marcou_estudado": False, "ultima_posicao": 15},
        )
        self.passar_tempo(10)
        response = self.enviar(segmentos=[2, 3, 4], posicao=25, segundos_assistidos=10)
        self.assertEqual(response.json()["percentual"], 25.0)

        progresso = ProgressoVideo.objects.get(usuario=self.usuario, video=self.video)
        self.assertEqual(progresso.segmentos_assistidos, [0, 1, 2, 3, 4])
        self.assertEqual(progresso.percentual, Decimal("25.00"))
        self.assertEqual(progresso.ultima_posicao_segundos, 25)
        self.assertEqual(progresso.segundos_assistidos_total, 25)

        sessao = SessaoVideo.objects.get()
        self.assertEqual(str(sessao.pk), self.sessao_id)
        self.assertEqual((sessao.inicio_segundos, sessao.fim_segundos), (0, 25))
        self.assertEqual(sessao.segundos_assistidos, 25)
        self.assertEqual(sessao.percentual_video, Decimal("25.00"))

        self.passar_tempo(10)
        self.enviar(sessao_id=str(uuid.uuid4()), segmentos=[10, 11], posicao=60, segundos_assistidos=10)
        self.assertEqual(SessaoVideo.objects.count(), 2)
        nova = SessaoVideo.objects.exclude(pk=self.sessao_id).get()
        self.assertEqual((nova.inicio_segundos, nova.fim_segundos), (50, 60))

    def test_blocos_fora_do_intervalo_sao_descartados_e_segundos_limitados(self):
        self.iniciar()
        self.passar_tempo(300)
        self.enviar(segmentos=[-1, 0, 19, 20, 500], posicao=999, segundos_assistidos=500)
        progresso = ProgressoVideo.objects.get()
        self.assertEqual(progresso.segmentos_assistidos, [0, 19])
        self.assertEqual(progresso.ultima_posicao_segundos, 100)
        self.assertEqual(progresso.segundos_assistidos_total, 60)

    def test_duracao_gravada_nao_muda_depois_da_primeira(self):
        self.iniciar(duracao=100.4)
        self.video.refresh_from_db()
        self.assertEqual(self.video.duracao_segundos, 100)
        self.passar_tempo(10)
        response = self.enviar(duracao=10, segmentos=[0, 1, 2, 3], posicao=20, segundos_assistidos=20)
        self.video.refresh_from_db()
        self.assertEqual(self.video.duracao_segundos, 100)
        self.assertEqual(response.json()["percentual"], 20.0)

    def test_progresso_forjado_numa_unica_requisicao_e_limitado(self):
        # Mesmo declarando 60 s e todos os blocos, o servidor só credita o tempo real.
        response = self.enviar(segmentos=list(range(20)), posicao=100, segundos_assistidos=60)
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(response.json()["percentual"], 20)
        self.assertEqual(ProgressoVideo.objects.get().segundos_assistidos_total, 0)
        self.assertFalse(ConteudoEstudado.objects.exists())

    def test_rajada_de_requisicoes_nao_acumula_credito(self):
        self.iniciar()
        for indice in range(20):
            self.enviar(sessao_id=str(uuid.uuid4()), segmentos=list(range(20)), posicao=100, segundos_assistidos=60)
        progresso = ProgressoVideo.objects.get()
        self.assertLessEqual(progresso.percentual, 20)
        self.assertFalse(progresso.concluido)
        self.assertFalse(ConteudoEstudado.objects.exists())

    def test_velocidade_ate_2x_e_aceita(self):
        self.iniciar()
        # 15 s de vídeo assistidos em 7,5 s de relógio (2x).
        self.passar_tempo(7.5)
        response = self.enviar(segmentos=[0, 1, 2], posicao=15, segundos_assistidos=15)
        self.assertEqual(response.json()["percentual"], 15.0)
        self.assertEqual(ProgressoVideo.objects.get().segundos_assistidos_total, 15)

    def test_ao_passar_de_95_por_cento_marca_conteudo_como_estudado(self):
        self.iniciar()
        self.assistir(list(range(18)))
        self.assertFalse(ConteudoEstudado.objects.exists())
        response = self.assistir([18])
        self.assertEqual(response.json()["percentual"], 95.0)
        self.assertTrue(response.json()["concluido"])
        self.assertTrue(response.json()["marcou_estudado"])
        self.assertTrue(ConteudoEstudado.objects.filter(usuario=self.usuario, conteudo=self.conteudo).exists())
        progresso = ProgressoVideo.objects.get()
        self.assertTrue(progresso.marcou_conteudo_estudado)
        self.assertIsNotNone(progresso.concluido_em)

        response = self.assistir([19])
        self.assertTrue(response.json()["concluido"])
        self.assertFalse(response.json()["marcou_estudado"])

    def test_conteudo_ja_marcado_nao_duplica(self):
        ConteudoEstudado.objects.create(usuario=self.usuario, conteudo=self.conteudo)
        self.iniciar()
        response = self.assistir(list(range(20)))
        self.assertTrue(response.json()["concluido"])
        self.assertFalse(response.json()["marcou_estudado"])
        self.assertEqual(ConteudoEstudado.objects.filter(usuario=self.usuario).count(), 1)
        self.assertFalse(ProgressoVideo.objects.get().marcou_conteudo_estudado)

    def test_desmarcar_manualmente_nao_e_desfeito_pelo_video(self):
        self.iniciar()
        self.assistir(list(range(20)))
        self.client.post(reverse("estudos:alternar_conteudo_estudado", args=[self.conteudo.pk]))
        self.assertFalse(ConteudoEstudado.objects.exists())

        response = self.assistir(list(range(20)), sessao_id=str(uuid.uuid4()))
        self.assertFalse(response.json()["marcou_estudado"])
        self.assertFalse(ConteudoEstudado.objects.exists())
        self.assertTrue(ProgressoVideo.objects.get().concluido)
        self.assertEqual(SessaoVideo.objects.count(), 2)

    def test_progresso_de_um_usuario_nao_afeta_outro(self):
        self.iniciar()
        self.assistir(list(range(20)))
        outro_cliente = self.client_class()
        outro_cliente.force_login(self.outro_usuario)
        response = self.enviar(cliente=outro_cliente, sessao_id=str(uuid.uuid4()), segmentos=[0], segundos_assistidos=5)
        self.assertEqual(response.json()["percentual"], 5.0)
        self.assertFalse(response.json()["concluido"])
        self.assertFalse(ConteudoEstudado.objects.filter(usuario=self.outro_usuario).exists())
        self.assertEqual(ProgressoVideo.objects.get(usuario=self.usuario).percentual, Decimal("100.00"))


class DuracaoVideoAdminTests(VideosTestMixin, TestCase):
    def test_admin_corrige_duracao_e_percentuais_sao_recalculados(self):
        video = self.criar_video(duracao=5)
        progresso = ProgressoVideo.objects.create(
            usuario=self.usuario, video=video, segmentos_assistidos=[0], percentual=100, concluido=True,
        )
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("videos_admin:editar", args=[video.pk]),
            {"conteudo": self.conteudo.pk, "ordem": 0, "ativo": "on", "duracao_segundos": 100},
            follow=True,
        )
        self.assertContains(response, "o progresso de 1 estudante(s) foi recalculado")
        video.refresh_from_db()
        progresso.refresh_from_db()
        self.assertEqual(video.duracao_segundos, 100)
        self.assertEqual(progresso.percentual, Decimal("5.00"))
        self.assertTrue(progresso.concluido)

    def test_duracao_invalida_e_recusada(self):
        video = self.criar_video(duracao=100)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("videos_admin:editar", args=[video.pk]),
            {"conteudo": self.conteudo.pk, "ordem": 0, "ativo": "on", "duracao_segundos": 0},
        )
        self.assertContains(response, "Informe uma duração entre 1 segundo e 6 horas.")
        video.refresh_from_db()
        self.assertEqual(video.duracao_segundos, 100)

    def test_duracao_em_branco_volta_a_ser_informada_pelo_player(self):
        video = self.criar_video(duracao=5)
        self.client.force_login(self.staff)
        self.client.post(
            reverse("videos_admin:editar", args=[video.pk]),
            {"conteudo": self.conteudo.pk, "ordem": 0, "ativo": "on", "duracao_segundos": ""},
        )
        video.refresh_from_db()
        self.assertIsNone(video.duracao_segundos)

    def test_formulario_de_criacao_nao_tem_duracao(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("videos_admin:criar"))
        self.assertNotIn("duracao_segundos", response.context["form"].fields)


class HistoricoVideosTests(VideosTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.video = self.criar_video(duracao=600)
        self.video_fisica = self.criar_video(OUTRO_ID, conteudo=self.conteudo_fisica, duracao=600)
        SessaoVideo.objects.create(
            id=uuid.uuid4(), usuario=self.usuario, video=self.video,
            inicio_segundos=65, fim_segundos=3725, segundos_assistidos=90, percentual_video=20,
        )
        SessaoVideo.objects.create(
            id=uuid.uuid4(), usuario=self.usuario, video=self.video_fisica,
            inicio_segundos=0, fim_segundos=30, segundos_assistidos=30, percentual_video=5,
        )
        SessaoVideo.objects.create(
            id=uuid.uuid4(), usuario=self.outro_usuario, video=self.video,
            inicio_segundos=0, fim_segundos=10, segundos_assistidos=10, percentual_video=1,
        )
        ProgressoVideo.objects.create(usuario=self.usuario, video=self.video, percentual=97, concluido=True)
        self.client.force_login(self.usuario)

    def test_mostra_apenas_sessoes_do_usuario_com_minutagem(self):
        response = self.client.get(reverse("videos:historico"))
        sessoes = list(response.context["page_obj"])
        self.assertEqual(len(sessoes), 2)
        self.assertTrue(all(sessao.usuario == self.usuario for sessao in sessoes))
        self.assertContains(response, "01:05 – 1:02:05")
        self.assertContains(response, "01:30")
        self.assertContains(response, "Concluído")
        self.assertContains(response, f"#video-{self.video.pk}")

    def test_filtro_por_materia(self):
        response = self.client.get(reverse("videos:historico") + "?materia=fisica")
        sessoes = list(response.context["page_obj"])
        self.assertEqual([sessao.video for sessao in sessoes], [self.video_fisica])

    def test_video_inativo_e_conteudo_despublicado_nao_tem_links(self):
        self.video.ativo = False
        self.video.save()
        self.conteudo.status = Conteudo.StatusConteudo.ARQUIVADO
        self.conteudo.save(update_fields=["status"])
        response = self.client.get(reverse("videos:historico"))
        self.assertNotContains(response, f"#video-{self.video.pk}")
        self.assertNotContains(response, reverse("curriculo:conteudo_detalhe", args=["matematica", "porcentagem"]))

    def test_estado_vazio_e_login_obrigatorio(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("videos:historico")), "Você ainda não assistiu a nenhum vídeo.")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("videos:historico")).status_code, 302)

    def test_link_na_sidebar_do_estudante(self):
        response = self.client.get(reverse("videos:historico"))
        self.assertContains(response, "Histórico de vídeos")


class PadroesImportacaoVideosTests(VideosTestMixin, TestCase):
    def test_json_de_padroes_inclui_videos(self):
        self.criar_video()
        self.client.force_login(self.staff)
        response = self.client.get(reverse("curriculo_admin:admin_padroes_importacao_json") + "?formato=json")
        dados = json.loads(response.content)
        self.assertEqual(dados["importadores"]["videos"]["campos_referencia"], ["materia", "conteudo"])
        self.assertEqual(
            dados["videos_existentes"],
            [{
                "materia": "matematica",
                "conteudo": "porcentagem",
                "youtube_id": YOUTUBE_ID,
                "titulo": f"Aula {YOUTUBE_ID}",
                "canal_nome": "Canal Oficial",
                "ativo": True,
            }],
        )

    def test_tela_de_padroes_mostra_videos_e_volta_para_importacao(self):
        self.criar_video()
        self.client.force_login(self.staff)
        response = self.client.get(reverse("curriculo_admin:admin_padroes_importacao_json") + "?origem=videos")
        self.assertContains(response, "Vídeos já cadastrados")
        self.assertContains(response, f'id="appBackButton" href="{reverse("videos_admin:importar_json")}"')
