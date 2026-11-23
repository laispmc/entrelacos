"""Regras para eventos, itens e imagens de capa."""
import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Evento, StatusEvento
from . import ErroNegocio

ASSINATURAS = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
}


def _detectar_tipo(cabecalho):
    for assinatura, tipo in ASSINATURAS.items():
        if cabecalho.startswith(assinatura):
            return tipo
    if cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WEBP":
        return "webp"
    return None


def ler_imagem(arquivo):
    """Valida o conteúdo real da imagem. Retorna (nome_unico, bytes, tipo)."""
    dados = arquivo.read()
    if len(dados) > current_app.config["MAX_IMAGE_SIZE"]:
        raise ErroNegocio("A imagem deve ter no máximo 3 MB.")
    tipo = _detectar_tipo(dados[:16])
    if tipo is None:
        raise ErroNegocio("O arquivo enviado não é uma imagem JPG, PNG ou WEBP válida.")

    base = secure_filename(os.path.splitext(arquivo.filename or "")[0])[:40] or "capa"
    return f"{uuid.uuid4().hex[:12]}-{base}.{tipo}", dados, tipo


def definir_capa(evento, arquivo):
    evento.imagem_capa, evento.imagem_dados, evento.imagem_tipo = ler_imagem(arquivo)


def eventos_abertos():
    return db.session.scalars(
        db.select(Evento).filter_by(status=StatusEvento.ABERTO).order_by(Evento.data)
    ).all()


def eventos_encerrados(limite=6):
    return db.session.scalars(
        db.select(Evento)
        .filter_by(status=StatusEvento.ENCERRADO)
        .order_by(Evento.data.desc())
        .limit(limite)
    ).all()


def validar_nova_quantidade(item, nova_quantidade):
    if nova_quantidade < item.quantidade_comprometida:
        raise ErroNegocio(
            f"A quantidade necessária não pode ser menor que o já comprometido "
            f"({item.quantidade_comprometida} {item.unidade})."
        )
