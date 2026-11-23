"""Blueprint de eventos: página pública do evento e gerenciamento (admin)."""
from flask import (
    Blueprint, Response, abort, current_app, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import AcaoSimplesForm, AdicionarCarrinhoForm, EventoForm, ItemForm, NovoEventoForm
from ..models import Evento, Item
from ..services import ErroNegocio
from ..services.eventos import definir_capa, validar_nova_quantidade

bp = Blueprint("eventos", __name__)


def _obter_evento(evento_id):
    evento = db.session.get(Evento, evento_id)
    if evento is None:
        abort(404)
    return evento


def _obter_item(evento, item_id):
    item = db.session.get(Item, item_id)
    if item is None or item.evento_id != evento.id:
        abort(404)
    return item


# ---------------------------------------------------------------- público

@bp.route("/<int:evento_id>")
def detalhe(evento_id):
    evento = _obter_evento(evento_id)
    return render_template(
        "eventos/detalhe.html",
        evento=evento,
        itens=evento.itens_ativos,
        form=AdicionarCarrinhoForm(),
    )


# ---------------------------------------------------------- gerenciamento

@bp.route("/gerenciar")
@login_required
def gerenciar():
    eventos = db.session.scalars(
        db.select(Evento).order_by(Evento.status, Evento.data.desc())
    ).all()
    return render_template("eventos/gerenciar.html", eventos=eventos)


@bp.route("/gerenciar/novo", methods=["GET", "POST"])
@login_required
def novo():
    form = NovoEventoForm()
    if form.validate_on_submit():
        evento = Evento(
            nome=form.nome.data.strip(),
            descricao=form.descricao.data,
            data=form.data.data,
            local=form.local.data,
            status=form.status.data,
            administrador_id=current_user.id,
        )
        try:
            definir_capa(evento, form.imagem_capa.data)
        except ErroNegocio as erro:
            form.imagem_capa.errors.append(str(erro))
        else:
            db.session.add(evento)
            db.session.commit()
            current_app.logger.info("Evento %s criado por admin %s", evento.id, current_user.id)
            flash("Evento cadastrado. Agora adicione os itens necessários.", "success")
            return redirect(url_for("eventos.administrar", evento_id=evento.id))
    return render_template("eventos/form_evento.html", form=form, evento=None)


@bp.route("/gerenciar/<int:evento_id>/editar", methods=["GET", "POST"])
@login_required
def editar(evento_id):
    evento = _obter_evento(evento_id)
    form = EventoForm(obj=evento)
    form._edicao = True
    if form.validate_on_submit():
        if form.imagem_capa.data:
            try:
                definir_capa(evento, form.imagem_capa.data)
            except ErroNegocio as erro:
                form.imagem_capa.errors.append(str(erro))
                return render_template("eventos/form_evento.html", form=form, evento=evento)
        evento.nome = form.nome.data.strip()
        evento.descricao = form.descricao.data
        evento.data = form.data.data
        evento.local = form.local.data
        evento.status = form.status.data
        db.session.commit()
        current_app.logger.info("Evento %s editado por admin %s", evento.id, current_user.id)
        flash("Evento atualizado.", "success")
        return redirect(url_for("eventos.administrar", evento_id=evento.id))
    return render_template("eventos/form_evento.html", form=form, evento=evento)


@bp.route("/gerenciar/<int:evento_id>")
@login_required
def administrar(evento_id):
    evento = _obter_evento(evento_id)
    return render_template(
        "eventos/administrar.html",
        evento=evento,
        form_item=ItemForm(),
        acao=AcaoSimplesForm(),
    )


@bp.route("/gerenciar/<int:evento_id>/itens/novo", methods=["POST"])
@login_required
def novo_item(evento_id):
    evento = _obter_evento(evento_id)
    form = ItemForm()
    if form.validate_on_submit():
        item = Item(
            evento=evento,
            nome=form.nome.data.strip(),
            descricao=form.descricao.data,
            quantidade_necessaria=form.quantidade_necessaria.data,
            unidade=form.unidade.data.strip(),
        )
        db.session.add(item)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um item com esse nome neste evento.", "danger")
        else:
            flash(f"Item “{item.nome}” adicionado.", "success")
        return redirect(url_for("eventos.administrar", evento_id=evento.id))
    return render_template(
        "eventos/administrar.html", evento=evento, form_item=form, acao=AcaoSimplesForm()
    ), 400


@bp.route("/gerenciar/<int:evento_id>/itens/<int:item_id>/editar", methods=["GET", "POST"])
@login_required
def editar_item(evento_id, item_id):
    evento = _obter_evento(evento_id)
    item = _obter_item(evento, item_id)
    form = ItemForm(obj=item)
    if form.validate_on_submit():
        try:
            validar_nova_quantidade(item, form.quantidade_necessaria.data)
        except ErroNegocio as erro:
            form.quantidade_necessaria.errors.append(str(erro))
        else:
            item.nome = form.nome.data.strip()
            item.descricao = form.descricao.data
            item.quantidade_necessaria = form.quantidade_necessaria.data
            item.unidade = form.unidade.data.strip()
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                form.nome.errors.append("Já existe um item com esse nome neste evento.")
            else:
                flash("Item atualizado.", "success")
                return redirect(url_for("eventos.administrar", evento_id=evento.id))
    return render_template("eventos/form_item.html", form=form, evento=evento, item=item)


@bp.route("/gerenciar/<int:evento_id>/itens/<int:item_id>/alternar", methods=["POST"])
@login_required
def alternar_item(evento_id, item_id):
    evento = _obter_evento(evento_id)
    item = _obter_item(evento, item_id)
    if AcaoSimplesForm().validate_on_submit():
        item.ativo = not item.ativo
        db.session.commit()
        flash(f"Item “{item.nome}” {'reativado' if item.ativo else 'desativado'}.", "info")
    return redirect(url_for("eventos.administrar", evento_id=evento.id))


@bp.route("/<int:evento_id>/capa/<nome>")
def capa(evento_id, nome):
    """Entrega a imagem de capa guardada no banco.

    O nome único faz parte da URL; quando a capa muda, a URL muda também,
    então o navegador e a CDN podem guardar a imagem em cache por muito tempo.
    """
    evento = _obter_evento(evento_id)
    if not evento.imagem_dados or nome != evento.imagem_capa:
        abort(404)
    tipo = "jpeg" if evento.imagem_tipo == "jpg" else evento.imagem_tipo
    resposta = Response(evento.imagem_dados, mimetype=f"image/{tipo}")
    resposta.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resposta


@bp.app_template_global()
def url_capa(evento):
    return url_for("eventos.capa", evento_id=evento.id, nome=evento.imagem_capa)


@bp.before_app_request
def _bloquear_admin_inativo():
    if request.endpoint and current_user.is_authenticated and not current_user.ativo:
        abort(403)
