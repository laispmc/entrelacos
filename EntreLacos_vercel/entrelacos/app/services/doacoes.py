"""Confirmação de doações e consulta pública das contribuições."""
from flask import current_app
from sqlalchemy import func, update

from ..extensions import db
from ..models import Doacao, DoacaoItem, Doador, Evento, Item
from ..utils import telefone_padrao
from . import ErroNegocio


def confirmar_doacao(evento_id, itens, nome, telefone, observacao=None):
    """Registra a doação dentro de uma única transação.

    `itens` é um dicionário {item_id: quantidade}. Se qualquer item não tiver
    mais a quantidade disponível, nada é gravado (rollback) e um ErroNegocio é lançado.
    """
    if not itens:
        raise ErroNegocio("Seu carrinho está vazio.")

    evento = db.session.get(Evento, evento_id)
    if evento is None or not evento.aberto:
        raise ErroNegocio("Este evento não está mais recebendo doações.")

    telefone = telefone_padrao(telefone)
    nome = " ".join(nome.split())

    try:
        indisponiveis = []
        for item_id, quantidade in itens.items():
            if quantidade <= 0:
                raise ErroNegocio("As quantidades devem ser maiores que zero.")
            # Reserva atômica: só atualiza se ainda couber na necessidade cadastrada
            resultado = db.session.execute(
                update(Item)
                .where(
                    Item.id == item_id,
                    Item.evento_id == evento.id,
                    Item.ativo.is_(True),
                    Item.quantidade_comprometida + quantidade <= Item.quantidade_necessaria,
                )
                .values(quantidade_comprometida=Item.quantidade_comprometida + quantidade)
                .execution_options(synchronize_session=False)
            )
            if resultado.rowcount != 1:
                item = db.session.get(Item, item_id)
                indisponiveis.append(item.nome if item else f"item #{item_id}")

        if indisponiveis:
            raise ErroNegocio(
                "Alguns itens não têm mais a quantidade escolhida disponível: "
                + ", ".join(indisponiveis)
                + ". Revise o carrinho e tente novamente."
            )

        doador = db.session.scalar(db.select(Doador).filter_by(telefone=telefone))
        if doador is None:
            doador = Doador(nome=nome, telefone=telefone)
            db.session.add(doador)
        else:
            doador.nome = nome

        doacao = Doacao(evento=evento, doador=doador, nome_informado=nome,
                        observacao=(observacao or "").strip() or None)
        for item_id, quantidade in itens.items():
            doacao.itens.append(DoacaoItem(item_id=item_id, quantidade_prometida=quantidade))
        db.session.add(doacao)
        db.session.commit()
    except ErroNegocio:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao confirmar doação no evento %s", evento_id)
        raise

    db.session.expire_all()
    current_app.logger.info(
        "Doação %s confirmada no evento %s (%d itens)", doacao.id, evento.id, len(itens)
    )
    return doacao


def buscar_por_nome(evento_id, nome):
    """Busca por parte do nome. `evento_id=None` pesquisa em todos os eventos."""
    termo = f"%{' '.join(nome.split())}%"
    consulta = db.select(Doacao).filter(Doacao.nome_informado.ilike(termo))
    if evento_id:
        consulta = consulta.filter(Doacao.evento_id == evento_id)
    return db.session.scalars(consulta.order_by(Doacao.criado_em.desc()).limit(30)).all()


def buscar_por_telefone(evento_id, telefone):
    """Busca pelo telefone exato. `evento_id=None` pesquisa em todos os eventos."""
    consulta = db.select(Doacao).join(Doador).filter(Doador.telefone == telefone_padrao(telefone))
    if evento_id:
        consulta = consulta.filter(Doacao.evento_id == evento_id)
    return db.session.scalars(consulta.order_by(Doacao.criado_em.desc())).all()


def resumo_publico_evento(evento_id):
    """Contagem de doações por situação (sem dados pessoais)."""
    linhas = db.session.execute(
        db.select(Doacao.status, func.count(Doacao.id))
        .filter(Doacao.evento_id == evento_id)
        .group_by(Doacao.status)
    ).all()
    return dict(linhas)
