"""Comandos de terminal para administradores."""
from app.extensions import db
from app.models import Administrador


def _senhas(monkeypatch, *respostas):
    respostas = iter(respostas)
    monkeypatch.delenv("ADMIN_SENHA", raising=False)
    monkeypatch.setattr("app.commands.getpass.getpass", lambda _msg="": next(respostas))


def test_criar_admin_com_senha_confirmada(app, monkeypatch):
    _senhas(monkeypatch, "senha-nova-123", "senha-nova-123")
    resultado = app.test_cli_runner().invoke(
        args=["criar-admin", "--nome", "Ana", "--email", "Ana@Exemplo.com"])
    assert "criado" in resultado.output
    admin = db.session.scalar(db.select(Administrador))
    assert admin.email == "ana@exemplo.com"
    assert admin.verificar_senha("senha-nova-123")


def test_criar_admin_recusa_senhas_diferentes(app, monkeypatch):
    _senhas(monkeypatch, "senha-nova-123", "senha-errada-123")
    resultado = app.test_cli_runner().invoke(
        args=["criar-admin", "--nome", "Ana", "--email", "ana@exemplo.com"])
    assert "não conferem" in resultado.output
    assert db.session.scalar(db.select(db.func.count(Administrador.id))) == 0


def test_redefinir_senha_permite_novo_login(app, client, admin, monkeypatch):
    _senhas(monkeypatch, "trocada-456789", "trocada-456789")
    resultado = app.test_cli_runner().invoke(
        args=["redefinir-senha", "--email", "admin@teste.com"])
    assert "redefinida" in resultado.output

    resposta = client.post("/admin/login", data={
        "email": "admin@teste.com", "senha": "trocada-456789",
    }, follow_redirects=True)
    assert "Painel de arrecadação" in resposta.get_data(as_text=True)


def test_redefinir_senha_de_email_inexistente(app, monkeypatch):
    _senhas(monkeypatch)
    resultado = app.test_cli_runner().invoke(
        args=["redefinir-senha", "--email", "ninguem@exemplo.com"])
    assert "Nenhum administrador" in resultado.output
