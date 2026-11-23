"""Blueprint administrativo: login, dashboard e gestão das doações."""
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms import AcaoSimplesForm, FiltroDoacoesForm, LoginForm, RecebimentoForm
from ..models import Administrador, Doacao, Doador, Evento, StatusDoacao
from ..services import ErroNegocio
from ..services.dashboard import indicadores_gerais, progresso_por_evento
from ..services.recebimentos import cancelar_pendencias, registrar_movimentacao
from ..utils import formatar_telefone

bp = Blueprint("admin", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        admin = db.session.scalar(
            db.select(Administrador).filter_by(email=form.email.data.strip().lower())
        )
        if admin and admin.ativo and admin.verificar_senha(form.senha.data):
            login_user(admin, remember=form.lembrar.data)
            current_app.logger.info("Login do administrador %s", admin.id)
            destino = request.args.get("next")
            if not destino or urlparse(destino).netloc or not destino.startswith("/"):
                destino = url_for("admin.dashboard")
            return redirect(destino)
        current_app.logger.warning("Tentativa de login inválida para %s", form.email.data)
        flash("E-mail ou senha incorretos.", "danger")
    return render_template("admin/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    if AcaoSimplesForm().validate_on_submit():
        logout_user()
        flash("Você saiu da área administrativa.", "info")
    return redirect(url_for("public.inicio"))


@bp.route("/")
@login_required
def dashboard():
    return render_template(
        "admin/dashboard.html",
        ind=indicadores_gerais(),
        progresso=progresso_por_evento(),
    )


@bp.route("/doacoes")
@login_required
def doacoes():
    form = FiltroDoacoesForm(request.args)
    eventos = db.session.scalars(db.select(Evento).order_by(Evento.data.desc())).all()
    form.evento.choices = [(0, "Todos os eventos")] + [(e.id, e.nome) for e in eventos]
    form.status.choices = [("", "Todas")] + list(StatusDoacao.ROTULOS.items())

    consulta = db.select(Doacao).join(Doador).order_by(Doacao.criado_em.desc())
    if form.evento.data:
        consulta = consulta.filter(Doacao.evento_id == form.evento.data)
    if form.status.data in StatusDoacao.TODOS:
        consulta = consulta.filter(Doacao.status == form.status.data)
    if form.busca.data:
        termo = form.busca.data.strip()
        digitos = "".join(ch for ch in termo if ch.isdigit())
        filtro = Doacao.nome_informado.ilike(f"%{termo}%")
        if len(digitos) >= 4:
            filtro = filtro | Doador.telefone.contains(digitos)
        consulta = consulta.filter(filtro)

    pagina = db.paginate(consulta, per_page=20, error_out=False)
    return render_template("admin/doacoes.html", form=form, pagina=pagina)


@bp.route("/doacoes/<int:doacao_id>", methods=["GET", "POST"])
@login_required
def doacao(doacao_id):
    doacao = db.session.get(Doacao, doacao_id)
    if doacao is None:
        abort(404)

    form = RecebimentoForm()
    if form.validate_on_submit():
        movimentos = {}
        try:
            for di in doacao.itens:
                recebido = _ler_inteiro(f"receber_{di.id}")
                cancelado = _ler_inteiro(f"cancelar_{di.id}")
                movimentos[di.id] = (recebido, cancelado)
            registrar_movimentacao(doacao, movimentos, form.token.data, current_user,
                                   form.observacao.data)
        except ErroNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Movimentação registrada.", "success")
            return redirect(url_for("admin.doacao", doacao_id=doacao.id))

    form.gerar_token()
    form.observacao.data = ""
    return render_template(
        "admin/doacao.html",
        doacao=doacao,
        form=form,
        form_cancelar=RecebimentoForm(formdata=None).gerar_token(),
        telefone=formatar_telefone(doacao.doador.telefone),
    )


@bp.route("/doacoes/<int:doacao_id>/cancelar", methods=["POST"])
@login_required
def cancelar(doacao_id):
    doacao = db.session.get(Doacao, doacao_id)
    if doacao is None:
        abort(404)
    form = RecebimentoForm()
    if form.validate_on_submit():
        try:
            cancelar_pendencias(doacao, form.token.data, current_user)
        except ErroNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Quantidades pendentes canceladas e liberadas para novas doações.", "info")
    return redirect(url_for("admin.doacao", doacao_id=doacao.id))


def _ler_inteiro(campo):
    valor = (request.form.get(campo) or "0").strip() or "0"
    try:
        numero = int(valor)
    except ValueError:
        raise ErroNegocio("Use apenas números inteiros nas quantidades.")
    if numero < 0:
        raise ErroNegocio("As quantidades não podem ser negativas.")
    return numero
