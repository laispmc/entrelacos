"""Registro de recebimentos parciais/totais e cancelamento de pendências."""
from flask import current_app
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Entrega, Item, Recebimento
from . import ErroNegocio


def registrar_movimentacao(doacao, movimentos, token, administrador, observacao=None):
    """Registra o que foi recebido e/ou cancelado em uma doação.

    `movimentos` é um dicionário {doacao_item_id: (recebido, cancelado)}.
    O `token` vem do formulário e é único: se o mesmo envio chegar duas vezes
    (duplo clique, recarregar a página), o segundo é recusado.
    """
    if not token:
        raise ErroNegocio("Formulário inválido. Recarregue a página.")
    if db.session.scalar(db.select(Entrega.id).filter_by(token=token)):
        raise ErroNegocio("Este registro já foi salvo anteriormente.")

    itens_por_id = {di.id: di for di in doacao.itens}
    movimentos = {k: v for k, v in movimentos.items() if v[0] or v[1]}
    if not movimentos:
        raise ErroNegocio("Informe ao menos uma quantidade recebida ou cancelada.")

    for doacao_item_id, (recebido, cancelado) in movimentos.items():
        doacao_item = itens_por_id.get(doacao_item_id)
        if doacao_item is None:
            raise ErroNegocio("Item não pertence a esta doação.")
        if recebido < 0 or cancelado < 0:
            raise ErroNegocio("As quantidades não podem ser negativas.")
        if recebido + cancelado > doacao_item.quantidade_pendente:
            raise ErroNegocio(
                f"{doacao_item.item.nome}: a quantidade informada ({recebido + cancelado}) "
                f"ultrapassa o pendente ({doacao_item.quantidade_pendente} "
                f"{doacao_item.item.unidade})."
            )

    so_cancelamento = all(rec == 0 for rec, _ in movimentos.values())
    entrega = Entrega(
        doacao=doacao,
        administrador_id=administrador.id,
        token=token,
        tipo="cancelamento" if so_cancelamento else "recebimento",
        observacao=(observacao or "").strip() or None,
    )
    try:
        for doacao_item_id, (recebido, cancelado) in movimentos.items():
            doacao_item = itens_por_id[doacao_item_id]
            doacao_item.quantidade_recebida += recebido
            doacao_item.quantidade_cancelada += cancelado
            if cancelado:
                # Apenas o cancelamento devolve quantidade para novas doações.
                # O recebimento não mexe na reserva, que já foi feita na confirmação.
                item = db.session.get(Item, doacao_item.item_id)
                item.quantidade_comprometida -= cancelado
            entrega.recebimentos.append(Recebimento(
                doacao_item=doacao_item,
                quantidade_recebida=recebido,
                quantidade_cancelada=cancelado,
            ))
        db.session.add(entrega)
        doacao.recalcular_status()
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        current_app.logger.warning("Registro duplicado ou inválido na doação %s", doacao.id)
        raise ErroNegocio("Não foi possível salvar: o registro já existe ou é inválido.")

    current_app.logger.info(
        "Doação %s: %s registrado por admin %s", doacao.id, entrega.tipo, administrador.id
    )
    return entrega


def cancelar_pendencias(doacao, token, administrador):
    """Cancela tudo o que ainda não foi recebido na doação."""
    movimentos = {
        di.id: (0, di.quantidade_pendente) for di in doacao.itens if di.quantidade_pendente > 0
    }
    if not movimentos:
        raise ErroNegocio("Esta doação não possui quantidades pendentes.")
    return registrar_movimentacao(
        doacao, movimentos, token, administrador, "Cancelamento das quantidades pendentes"
    )
