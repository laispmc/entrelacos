"""Indicadores do painel administrativo (consultas com agregações)."""
from sqlalchemy import case, func

from ..extensions import db
from ..models import Doacao, DoacaoItem, Evento, Item, StatusDoacao, StatusEvento


def indicadores_gerais():
    eventos_ativos = db.session.scalar(
        db.select(func.count(Evento.id)).filter_by(status=StatusEvento.ABERTO)
    )

    por_status = dict(db.session.execute(
        db.select(Doacao.status, func.count(Doacao.id)).group_by(Doacao.status)
    ).all())

    # Itens de eventos abertos que ainda não estão totalmente comprometidos
    itens_necessarios = db.session.scalar(
        db.select(func.count(Item.id))
        .join(Evento)
        .filter(
            Evento.status == StatusEvento.ABERTO,
            Item.ativo.is_(True),
            Item.quantidade_comprometida < Item.quantidade_necessaria,
        )
    )

    # Linhas de itens com entrega pendente (diferente do número de doações)
    itens_aguardando = db.session.scalar(
        db.select(func.count(DoacaoItem.id)).filter(
            DoacaoItem.quantidade_recebida + DoacaoItem.quantidade_cancelada
            < DoacaoItem.quantidade_prometida
        )
    )

    return {
        "eventos_ativos": eventos_ativos,
        "doacoes_total": sum(por_status.values()),
        "doacoes_pendentes": por_status.get(StatusDoacao.PENDENTE, 0),
        "doacoes_parciais": por_status.get(StatusDoacao.PARCIAL, 0),
        "doacoes_recebidas": por_status.get(StatusDoacao.RECEBIDA, 0),
        "doacoes_canceladas": por_status.get(StatusDoacao.CANCELADA, 0),
        "itens_necessarios": itens_necessarios,
        "itens_aguardando_entrega": itens_aguardando,
    }


def progresso_por_evento():
    """Para cada evento: total necessário, comprometido e recebido (média por item)."""
    recebido_por_item = (
        db.select(
            DoacaoItem.item_id.label("item_id"),
            func.sum(DoacaoItem.quantidade_recebida).label("recebido"),
        )
        .group_by(DoacaoItem.item_id)
        .subquery()
    )

    linhas = db.session.execute(
        db.select(
            Evento,
            func.count(Item.id).label("qtd_itens"),
            func.avg(
                1.0 * Item.quantidade_comprometida / Item.quantidade_necessaria
            ).label("comprometido"),
            func.avg(
                1.0 * func.coalesce(recebido_por_item.c.recebido, 0) / Item.quantidade_necessaria
            ).label("recebido"),
            func.sum(
                case((Item.quantidade_comprometida < Item.quantidade_necessaria, 1), else_=0)
            ).label("faltando"),
        )
        .outerjoin(Item, (Item.evento_id == Evento.id) & Item.ativo.is_(True))
        .outerjoin(recebido_por_item, recebido_por_item.c.item_id == Item.id)
        .group_by(Evento.id)
        .order_by(Evento.status, Evento.data)
    ).all()

    contagem_doacoes = dict(db.session.execute(
        db.select(Doacao.evento_id, func.count(Doacao.id)).group_by(Doacao.evento_id)
    ).all())

    return [
        {
            "evento": evento,
            "qtd_itens": qtd_itens,
            "comprometido": round(100 * (comprometido or 0)),
            "recebido": round(100 * (recebido or 0)),
            "faltando": faltando or 0,
            "doacoes": contagem_doacoes.get(evento.id, 0),
        }
        for evento, qtd_itens, comprometido, recebido, faltando in linhas
    ]
