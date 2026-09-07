import ipaddress
import logging
import socket
import uuid
from urllib.parse import urlparse

import cloudinary.api
import cloudinary.uploader
from cloudinary import CloudinaryImage
from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)

FORMATOS_PERMITIDOS = {"jpg", "jpeg", "png", "webp"}
CONTENT_TYPES_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
TAMANHO_MAXIMO_BYTES = 8 * 1024 * 1024
PASTA_BASE = "plataforma-estudos/questoes"


def _public_id_unico(prefixo):
    prefixo = (prefixo or "").strip("/")
    if prefixo == "questoes":
        return f"{PASTA_BASE}/{uuid.uuid4().hex}"
    return f"{PASTA_BASE}/{prefixo}/{uuid.uuid4().hex}"


def _validar_resultado_cloudinary(resultado):
    formato = (resultado.get("format") or "").lower()
    if resultado.get("resource_type") != "image" or formato not in FORMATOS_PERMITIDOS:
        raise ValidationError("Formato de imagem inválido. Use JPEG, PNG ou WebP.")
    if resultado.get("bytes") and resultado["bytes"] > TAMANHO_MAXIMO_BYTES:
        raise ValidationError("A imagem deve ter no máximo 8 MB.")
    public_id = resultado.get("public_id")
    if not public_id:
        raise ValidationError("Cloudinary não retornou a referência da imagem.")
    return public_id


def validar_public_id(public_id):
    public_id = (public_id or "").strip()
    if not public_id:
        raise ValidationError("Informe o public_id da imagem.")
    if public_id.startswith(("http://", "https://")):
        raise ValidationError("Informe apenas o public_id do Cloudinary, não a URL completa.")
    if any(char in public_id for char in ["\\", "?", "#"]):
        raise ValidationError("Public_id de imagem inválido.")
    try:
        cloudinary.api.resource(public_id, resource_type="image")
    except Exception as exc:
        logger.warning("Falha ao validar imagem Cloudinary '%s': %s", public_id, exc)
        raise ValidationError(f'Imagem Cloudinary "{public_id}" não encontrada.') from exc
    return public_id


def gerar_url_imagem(public_id):
    if not public_id:
        return ""
    try:
        return CloudinaryImage(public_id).build_url(secure=True)
    except ValueError as exc:
        logger.debug("Cloudinary não está configurado para gerar URL de imagem: %s", exc)
        return ""


def upload_imagem_arquivo(arquivo, prefixo="questoes"):
    if not arquivo:
        return ""
    if arquivo.size > TAMANHO_MAXIMO_BYTES:
        raise ValidationError("A imagem deve ter no máximo 8 MB.")
    if getattr(arquivo, "content_type", "") not in CONTENT_TYPES_PERMITIDOS:
        raise ValidationError("Formato de imagem inválido. Use JPEG, PNG ou WebP.")
    try:
        resultado = cloudinary.uploader.upload(
            arquivo,
            public_id=_public_id_unico(prefixo),
            resource_type="image",
            overwrite=False,
            allowed_formats=list(FORMATOS_PERMITIDOS),
            timeout=20,
        )
    except Exception as exc:
        logger.exception("Falha ao enviar imagem ao Cloudinary.")
        raise ValidationError("Não foi possível enviar a imagem ao Cloudinary.") from exc
    return _validar_resultado_cloudinary(resultado)


def _host_eh_bloqueado(hostname):
    if hostname.lower() in {"localhost", "localhost.localdomain"}:
        return True
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValidationError("Não foi possível validar o endereço da imagem.") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def validar_url_imagem(url):
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("Informe uma URL http ou https válida.")
    if _host_eh_bloqueado(parsed.hostname or ""):
        raise ValidationError("A URL da imagem não pode apontar para rede local ou privada.")
    return url


def upload_imagem_url(url, prefixo="questoes"):
    url = validar_url_imagem(url)
    try:
        resultado = cloudinary.uploader.upload(
            url,
            public_id=_public_id_unico(prefixo),
            resource_type="image",
            overwrite=False,
            allowed_formats=list(FORMATOS_PERMITIDOS),
            timeout=20,
        )
    except Exception as exc:
        logger.exception("Falha ao importar imagem por URL no Cloudinary.")
        raise ValidationError("Não foi possível importar a imagem informada.") from exc
    return _validar_resultado_cloudinary(resultado)
