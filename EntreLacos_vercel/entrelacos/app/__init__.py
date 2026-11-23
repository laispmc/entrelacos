"""Application Factory do EntreLaços."""
import os
import sqlite3

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from config import config_por_nome

from .extensions import csrf, db, login_manager


@event.listens_for(Engine, "connect")
def _ativar_chaves_estrangeiras(dbapi_connection, _record):
    """O SQLite só respeita FOREIGN KEY quando essa opção é ligada por conexão."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return  # Postgres já respeita as chaves estrangeiras
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_app(nome_config=None):
    nome_config = (nome_config or os.environ.get("FLASK_CONFIG")
                   or ("production" if os.environ.get("VERCEL") else "development"))
    # Arquivos estáticos ficam em public/static: na Vercel a CDN serve essa pasta
    # direto; localmente o próprio Flask serve o mesmo endereço /static/...
    app = Flask(__name__, static_folder="../public/static", static_url_path="/static")
    app.config.from_object(config_por_nome[nome_config])

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY não definida. Copie .env.example para .env e preencha a chave."
        )

    if not os.environ.get("VERCEL"):
        # Pasta do banco SQLite local (na Vercel o disco é somente leitura)
        try:
            os.makedirs(os.path.join(app.root_path, "..", "instance"), exist_ok=True)
        except OSError:
            pass

    # Os logs vão para o terminal (localmente) ou para os Runtime Logs (Vercel)
    app.logger.setLevel(app.config["LOG_LEVEL"])

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    _registrar_blueprints(app)
    _registrar_erros(app)
    _registrar_filtros(app)

    from .commands import registrar_comandos

    registrar_comandos(app)

    with app.app_context():
        from . import models  # noqa: F401  (registra as tabelas)

        db.create_all()
        _criar_admin_inicial(app)

    app.logger.info("Aplicação iniciada com a configuração '%s'", nome_config)
    return app


def _registrar_blueprints(app):
    from .blueprints.admin import bp as admin_bp
    from .blueprints.doacoes import bp as doacoes_bp
    from .blueprints.eventos import bp as eventos_bp
    from .blueprints.public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(eventos_bp, url_prefix="/eventos")
    app.register_blueprint(doacoes_bp, url_prefix="/doacoes")
    app.register_blueprint(admin_bp, url_prefix="/admin")


def _criar_admin_inicial(app):
    """Cria o primeiro administrador a partir de ADMIN_EMAIL / ADMIN_SENHA, se definidos.

    Útil na Vercel, onde não há terminal para rodar `flask criar-admin`.
    """
    from .models import Administrador

    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    senha = os.environ.get("ADMIN_SENHA") or ""
    if app.testing or not email or len(senha) < 8:
        return
    if db.session.scalar(db.select(Administrador.id).filter_by(email=email)):
        return
    admin = Administrador(nome=os.environ.get("ADMIN_NOME", "Administrador"), email=email)
    admin.definir_senha(senha)
    db.session.add(admin)
    try:
        db.session.commit()
    except IntegrityError:  # outra instância criou ao mesmo tempo
        db.session.rollback()
        return
    app.logger.info("Administrador inicial %s criado a partir das variáveis de ambiente", email)


def _registrar_erros(app):
    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return render_template("erros/erro.html", codigo=404,
                               titulo="Página não encontrada",
                               mensagem="O endereço acessado não existe ou foi removido."), 404

    @app.errorhandler(403)
    def proibido(_erro):
        return render_template("erros/erro.html", codigo=403,
                               titulo="Acesso negado",
                               mensagem="Você não tem permissão para acessar esta página."), 403

    @app.errorhandler(413)
    def arquivo_grande(_erro):
        return render_template("erros/erro.html", codigo=413,
                               titulo="Arquivo muito grande",
                               mensagem="O arquivo enviado ultrapassa o limite permitido."), 413

    @app.errorhandler(CSRFError)
    def erro_csrf(_erro):
        app.logger.warning("Falha de CSRF em requisição")
        return render_template("erros/erro.html", codigo=400,
                               titulo="Formulário expirado",
                               mensagem="Recarregue a página e tente enviar novamente."), 400

    @app.errorhandler(500)
    def erro_interno(erro):
        db.session.rollback()
        app.logger.exception("Erro interno: %s", erro)
        return render_template("erros/erro.html", codigo=500,
                               titulo="Algo deu errado",
                               mensagem="Ocorreu um erro inesperado. Tente novamente em instantes."), 500


def _registrar_filtros(app):
    from .utils import formatar_data, formatar_quantidade

    app.jinja_env.filters["data_br"] = formatar_data
    app.jinja_env.filters["qtd"] = formatar_quantidade

    @app.context_processor
    def injetar_carrinho():
        from .services.carrinho import total_itens_carrinho

        return {"carrinho_qtd": total_itens_carrinho()}
