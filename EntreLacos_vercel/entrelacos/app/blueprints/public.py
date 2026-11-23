"""Blueprint público: página inicial e páginas institucionais."""
from flask import Blueprint, render_template

from ..services.eventos import eventos_abertos, eventos_encerrados

bp = Blueprint("public", __name__)


@bp.route("/")
def inicio():
    return render_template(
        "public/inicio.html",
        eventos=eventos_abertos(),
        encerrados=eventos_encerrados(),
    )


@bp.route("/como-funciona")
def como_funciona():
    return render_template("public/como_funciona.html")
