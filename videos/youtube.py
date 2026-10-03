import json
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from django.core.exceptions import ValidationError

from .models import YOUTUBE_ID_REGEX


OEMBED_URL = "https://www.youtube.com/oembed?format=json&url={url}"
USER_AGENT = "PlataformaEstudosENEM/1.0 (curadoria de videos)"
TIMEOUT_SEGUNDOS = 5

HOSTS_YOUTUBE = {"youtube.com", "www.youtube.com", "m.youtube.com"}
HOSTS_YOUTU_BE = {"youtu.be", "www.youtu.be"}
HOSTS_NOCOOKIE = {"youtube-nocookie.com", "www.youtube-nocookie.com"}
PREFIXOS_CAMINHO = ("shorts", "embed", "live")

ERRO_LINK = "Link do YouTube inválido."
ERRO_PRIVADO = "O vídeo é privado ou o autor não permite incorporá-lo em outros sites."
ERRO_NAO_ENCONTRADO = "Vídeo não encontrado. Ele pode ter sido removido ou o link está incorreto."
ERRO_REDE = "Não foi possível consultar o YouTube agora. Tente novamente em instantes."
ERRO_AUTORIA = "O YouTube não retornou os dados de autoria do vídeo."

_id_valido = re.compile(YOUTUBE_ID_REGEX)


def _validar_id(youtube_id):
    if youtube_id and _id_valido.match(youtube_id):
        return youtube_id
    raise ValidationError(ERRO_LINK)


def extrair_youtube_id(texto):
    texto = (texto or "").strip()
    if _id_valido.match(texto):
        return texto
    if "://" not in texto:
        texto = f"https://{texto}"
    try:
        url = urlparse(texto)
    except ValueError:
        raise ValidationError(ERRO_LINK)
    if url.scheme not in {"http", "https"}:
        raise ValidationError(ERRO_LINK)

    host = (url.hostname or "").lower()
    partes = [parte for parte in url.path.split("/") if parte]

    if host in HOSTS_YOUTU_BE:
        return _validar_id(partes[0] if len(partes) == 1 else "")
    if host in HOSTS_NOCOOKIE:
        if len(partes) == 2 and partes[0] == "embed":
            return _validar_id(partes[1])
        raise ValidationError(ERRO_LINK)
    if host in HOSTS_YOUTUBE:
        if partes == ["watch"]:
            return _validar_id((parse_qs(url.query).get("v") or [""])[0])
        if len(partes) == 2 and partes[0] in PREFIXOS_CAMINHO:
            return _validar_id(partes[1])
    raise ValidationError(ERRO_LINK)


def buscar_metadados_youtube(youtube_id):
    youtube_id = _validar_id(youtube_id)
    url_video = f"https://www.youtube.com/watch?v={youtube_id}"
    requisicao = Request(
        OEMBED_URL.format(url=quote(url_video, safe="")),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise ValidationError(ERRO_PRIVADO)
        if exc.code in (400, 404):
            raise ValidationError(ERRO_NAO_ENCONTRADO)
        raise ValidationError(ERRO_REDE)
    except (URLError, socket.timeout, TimeoutError, OSError):
        raise ValidationError(ERRO_REDE)
    except (ValueError, UnicodeDecodeError):
        raise ValidationError(ERRO_AUTORIA)

    if not isinstance(dados, dict):
        raise ValidationError(ERRO_AUTORIA)
    titulo = dados.get("title")
    canal_nome = dados.get("author_name")
    canal_url = dados.get("author_url")
    if not all(isinstance(valor, str) and valor.strip() for valor in (titulo, canal_nome, canal_url)):
        raise ValidationError(ERRO_AUTORIA)
    thumbnail_url = dados.get("thumbnail_url")
    if not isinstance(thumbnail_url, str) or not thumbnail_url.strip():
        thumbnail_url = f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg"
    return {
        "titulo": titulo.strip()[:255],
        "canal_nome": canal_nome.strip()[:255],
        "canal_url": canal_url.strip()[:500],
        "thumbnail_url": thumbnail_url.strip()[:500],
    }
