"""Carrinho de doações guardado na sessão do navegador.

Estrutura na sessão: {"evento_id": 3, "itens": {"12": 2, "15": 5}}
O carrinho pertence a um único evento.
"""
from flask import session

from ..extensions import db
from ..models import Evento, Item
from . import ErroNegocio

CHAVE = "carrinho"


def obter_carrinho():
    return session.get(CHAVE) or {"evento_id": None, "itens": {}}


def _salvar(carrinho):
    session[CHAVE] = carrinho
    session.modified = True


def esvaziar_carrinho():
    session.pop(CHAVE, None)


def total_itens_carrinho():
    return len(obter_carrinho()["itens"])


def adicionar_item(item, quantidade):
    if quantidade <= 0:
        raise ErroNegocio("Informe uma quantidade maior que zero.")
    if not item.evento.aberto or not item.ativo:
        raise ErroNegocio("Este item não está mais recebendo doações.")

    carrinho = obter_carrinho()
    if carrinho["evento_id"] not in (None, item.evento_id) and carrinho["itens"]:
        raise ErroNegocio(
            "Seu carrinho já tem itens de outro evento. Confirme ou esvazie o carrinho "
            "antes de contribuir com este evento."
        )

    atual = carrinho["itens"].get(str(item.id), 0)
    nova = atual + quantidade
    if nova > item.quantidade_disponivel:
        raise ErroNegocio(
            f"Só restam {item.quantidade_disponivel} {item.unidade} de {item.nome} disponíveis."
        )

    carrinho["evento_id"] = item.evento_id
    carrinho["itens"][str(item.id)] = nova
    _salvar(carrinho)


def alterar_quantidade(item_id, quantidade):
    carrinho = obter_carrinho()
    chave = str(item_id)
    if chave not in carrinho["itens"]:
        raise ErroNegocio("Item não encontrado no carrinho.")
    if quantidade <= 0:
        remover_item(item_id)
        return
    item = db.session.get(Item, item_id)
    if item is None:
        remover_item(item_id)
        raise ErroNegocio("Este item não existe mais.")
    if quantidade > item.quantidade_disponivel:
        raise ErroNegocio(
            f"Só restam {item.quantidade_disponivel} {item.unidade} de {item.nome} disponíveis."
        )
    carrinho["itens"][chave] = quantidade
    _salvar(carrinho)


def remover_item(item_id):
    carrinho = obter_carrinho()
    carrinho["itens"].pop(str(item_id), None)
    if not carrinho["itens"]:
        carrinho["evento_id"] = None
    _salvar(carrinho)


def resumo_carrinho():
    """Retorna (evento, linhas) com os objetos do banco já carregados."""
    carrinho = obter_carrinho()
    if not carrinho["itens"]:
        return None, []
    evento = db.session.get(Evento, carrinho["evento_id"])
    if evento is None:
        esvaziar_carrinho()
        return None, []

    linhas = []
    for item_id, quantidade in carrinho["itens"].items():
        item = db.session.get(Item, int(item_id))
        if item is None or item.evento_id != evento.id:
            continue
        linhas.append({
            "item": item,
            "quantidade": quantidade,
            "excede": quantidade > item.quantidade_disponivel or not item.ativo,
        })
    linhas.sort(key=lambda linha: linha["item"].nome)
    return evento, linhas
