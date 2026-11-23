"""Configuração dos testes: banco SQLite em memória, separado do banco real.

Execute `pytest` na pasta do projeto (onde fica main.py).
"""
import io
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Administrador, Evento, Item, StatusEvento  # noqa: E402

PNG_MINIMO = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin(app):
    admin = Administrador(nome="Organizadora Teste", email="admin@teste.com")
    admin.definir_senha("senha-segura-123")
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def evento(app, admin):
    evento = Evento(
        nome="Almoço solidário",
        descricao="Evento de teste",
        data=date.today() + timedelta(days=10),
        local="Salão",
        imagem_capa="capa.png",
        status=StatusEvento.ABERTO,
        administrador=admin,
    )
    evento.itens.append(Item(nome="Arroz", quantidade_necessaria=10, unidade="kg"))
    evento.itens.append(Item(nome="Feijão", quantidade_necessaria=6, unidade="kg"))
    db.session.add(evento)
    db.session.commit()
    return evento


@pytest.fixture
def login(client, admin):
    def _login():
        return client.post("/admin/login", data={
            "email": "admin@teste.com", "senha": "senha-segura-123",
        }, follow_redirects=True)
    return _login


@pytest.fixture
def imagem_png():
    return lambda: (io.BytesIO(PNG_MINIMO), "capa.png")


def item_por_nome(evento, nome):
    return next(i for i in evento.itens if i.nome == nome)


def doar(client, item, quantidade, nome="Maria Souza", telefone="(27) 99999-1234", obs=""):
    """Adiciona um item ao carrinho e confirma a doação."""
    client.post("/doacoes/carrinho/adicionar", data={"item_id": item.id, "quantidade": quantidade})
    return client.post("/doacoes/confirmar", data={
        "nome": nome, "telefone": telefone, "observacao": obs,
    }, follow_redirects=True)
