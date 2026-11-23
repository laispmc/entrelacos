"""Blueprint de doações: carrinho, confirmação e consulta pública."""
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from ..extensions import db
from ..forms import (
    AcaoSimplesForm, AcompanharDoacaoForm, AdicionarCarrinhoForm, AlterarCarrinhoForm, ConfirmacaoDoacaoForm,
    PesquisaDoacaoForm,
)
from ..models import Doacao, Evento, Item, StatusDoacao
from ..services import ErroNegocio
from ..services import carrinho as servico_carrinho
from ..services.doacoes import (
    buscar_por_nome, buscar_por_telefone, confirmar_doacao, resumo_publico_evento,
)

bp = Blueprint("doacoes", __name__)


# --------------------------------------------------------------- carrinho

@bp.route("/carrinho")
def carrinho():
    evento, linhas = servico_carrinho.resumo_carrinho()
    return render_template(
        "doacoes/carrinho.html",
        evento=evento,
        linhas=linhas,
        form_qtd=AlterarCarrinhoForm(),
        acao=AcaoSimplesForm(),
    )


@bp.route("/carrinho/adicionar", methods=["POST"])
def adicionar():
    form = AdicionarCarrinhoForm()
    item = db.session.get(Item, int(form.item_id.data)) if (form.item_id.data or "").isdigit() else None
    if item is None:
        abort(404)
    if form.validate_on_submit():
        try:
            servico_carrinho.adicionar_item(item, form.quantidade.data)
        except ErroNegocio as erro:
            flash(str(erro), "warning")
        else:
            flash(f"{form.quantidade.data} {item.unidade} de {item.nome} no carrinho.", "success")
    else:
        flash("Informe uma quantidade maior que zero.", "warning")
    return redirect(url_for("eventos.detalhe", evento_id=item.evento_id) + "#itens")


@bp.route("/carrinho/<int:item_id>/alterar", methods=["POST"])
def alterar(item_id):
    form = AlterarCarrinhoForm()
    if form.validate_on_submit():
        try:
            servico_carrinho.alterar_quantidade(item_id, form.quantidade.data)
        except ErroNegocio as erro:
            flash(str(erro), "warning")
    else:
        flash("Quantidade inválida.", "warning")
    return redirect(url_for("doacoes.carrinho"))


@bp.route("/carrinho/<int:item_id>/remover", methods=["POST"])
def remover(item_id):
    if AcaoSimplesForm().validate_on_submit():
        servico_carrinho.remover_item(item_id)
        flash("Item removido do carrinho.", "info")
    return redirect(url_for("doacoes.carrinho"))


@bp.route("/carrinho/esvaziar", methods=["POST"])
def esvaziar():
    if AcaoSimplesForm().validate_on_submit():
        servico_carrinho.esvaziar_carrinho()
        flash("Carrinho esvaziado.", "info")
    return redirect(request.form.get("voltar") or url_for("doacoes.carrinho"))


# ------------------------------------------------------------ confirmação

@bp.route("/confirmar", methods=["GET", "POST"])
def confirmar():
    evento, linhas = servico_carrinho.resumo_carrinho()
    if not linhas:
        flash("Seu carrinho está vazio.", "info")
        return redirect(url_for("public.inicio"))
    if not evento.aberto:
        flash("Este evento foi encerrado e não recebe mais doações.", "warning")
        return redirect(url_for("doacoes.carrinho"))

    form = ConfirmacaoDoacaoForm()
    if form.validate_on_submit():
        itens = {linha["item"].id: linha["quantidade"] for linha in linhas}
        try:
            doacao = confirmar_doacao(
                evento.id, itens, form.nome.data, form.telefone.data, form.observacao.data
            )
        except ErroNegocio as erro:
            flash(str(erro), "danger")
            return redirect(url_for("doacoes.carrinho"))
        servico_carrinho.esvaziar_carrinho()
        session["ultima_doacao"] = doacao.id
        return redirect(url_for("doacoes.sucesso", doacao_id=doacao.id))

    return render_template("doacoes/confirmar.html", evento=evento, linhas=linhas, form=form)


@bp.route("/obrigado/<int:doacao_id>")
def sucesso(doacao_id):
    # Só quem acabou de doar vê o comprovante
    if session.get("ultima_doacao") != doacao_id:
        abort(404)
    doacao = db.session.get(Doacao, doacao_id)
    if doacao is None:
        abort(404)
    return render_template("doacoes/sucesso.html", doacao=doacao)


# --------------------------------------------------------------- consulta

@bp.route("/acompanhar", methods=["GET", "POST"])
def acompanhar():
    """Consulta geral, acessível pelo menu: procura em todos os eventos ou em um só."""
    eventos = db.session.scalars(
        db.select(Evento).order_by(Evento.status, Evento.data.desc())
    ).all()
    form = AcompanharDoacaoForm()
    form.evento.choices = [(0, "Todos os eventos")] + [
        (e.id, e.nome if e.aberto else f"{e.nome} (encerrado)") for e in eventos
    ]
    if request.method == "GET" and request.args.get("evento", "").isdigit():
        form.evento.data = int(request.args["evento"])

    resultados = None
    if form.validate_on_submit():
        evento_id = form.evento.data or None
        if form.tipo.data == "telefone":
            resultados = buscar_por_telefone(evento_id, form.termo.data)
            form.termo.data = ""  # o telefone não volta para a tela
        else:
            resultados = buscar_por_nome(evento_id, form.termo.data)

    return render_template("doacoes/acompanhar.html", form=form, resultados=resultados)


@bp.route("/evento/<int:evento_id>/consulta", methods=["GET", "POST"])
def consulta(evento_id):
    evento = db.session.get(Evento, evento_id)
    if evento is None:
        abort(404)

    form = PesquisaDoacaoForm()
    resultados = None
    if form.validate_on_submit():
        if form.tipo.data == "telefone":
            resultados = buscar_por_telefone(evento.id, form.termo.data)
            form.termo.data = ""  # o telefone não volta para a tela
        else:
            resultados = buscar_por_nome(evento.id, form.termo.data)

    return render_template(
        "doacoes/consulta.html",
        evento=evento,
        form=form,
        resultados=resultados,
        resumo=resumo_publico_evento(evento.id),
        Status=StatusDoacao,
    )
