"""Área administrativa: acesso, eventos, recebimentos e cancelamentos."""
import uuid

import pytest

from app.extensions import db
from app.models import Doacao, Evento, StatusDoacao

from conftest import doar, item_por_nome


@pytest.mark.parametrize("rota", ["/admin/", "/admin/doacoes", "/eventos/gerenciar",
                                  "/eventos/gerenciar/novo"])
def test_rota_administrativa_sem_login_redireciona(client, rota):
    resposta = client.get(rota)
    assert resposta.status_code == 302
    assert "/admin/login" in resposta.headers["Location"]


def test_login_com_senha_errada_e_recusado(client, admin):
    resposta = client.post("/admin/login", data={"email": "admin@teste.com", "senha": "errada"},
                           follow_redirects=True)
    assert "E-mail ou senha incorretos" in resposta.get_data(as_text=True)


def test_senha_armazenada_com_hash(admin):
    assert admin.senha_hash != "senha-segura-123"
    assert admin.verificar_senha("senha-segura-123")


def test_login_e_dashboard(client, login, evento):
    resposta = login()
    html = resposta.get_data(as_text=True)
    assert "Painel de arrecadação" in html
    assert "Almoço solidário" in html


def test_cadastrar_evento_com_imagem(client, login, imagem_png):
    login()
    resposta = client.post("/eventos/gerenciar/novo", data={
        "nome": "Bazar beneficente", "descricao": "", "data": "2099-01-01",
        "local": "", "status": "aberto", "imagem_capa": imagem_png(),
    }, content_type="multipart/form-data", follow_redirects=True)
    html = resposta.get_data(as_text=True)
    assert "Informe uma data dentro dos próximos 5 anos" in html  # data muito distante

    resposta = client.post("/eventos/gerenciar/novo", data={
        "nome": "Bazar beneficente", "descricao": "", "data": "2030-01-01",
        "local": "", "status": "aberto", "imagem_capa": imagem_png(),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert "Evento cadastrado" in resposta.get_data(as_text=True)
    evento = db.session.scalar(db.select(Evento).filter_by(nome="Bazar beneficente"))
    assert evento is not None

    # A capa fica guardada no banco e é servida por uma rota própria
    capa = client.get(f"/eventos/{evento.id}/capa/{evento.imagem_capa}")
    assert capa.status_code == 200
    assert capa.mimetype == "image/png"
    assert capa.data.startswith(b"\x89PNG")
    assert client.get(f"/eventos/{evento.id}/capa/outro-nome.png").status_code == 404


def test_cadastro_de_evento_rejeita_arquivo_que_nao_e_imagem(client, login):
    import io
    login()
    resposta = client.post("/eventos/gerenciar/novo", data={
        "nome": "Evento falso", "data": "2030-01-01", "status": "aberto",
        "imagem_capa": (io.BytesIO(b"isto nao e uma imagem"), "capa.png"),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert "não é uma imagem" in resposta.get_data(as_text=True)


def test_cadastrar_item_com_quantidade_zero_e_rejeitado(client, login, evento):
    login()
    resposta = client.post(f"/eventos/gerenciar/{evento.id}/itens/novo", data={
        "nome": "Açúcar", "quantidade_necessaria": 0, "unidade": "kg",
    })
    assert resposta.status_code == 400
    assert "maior que zero" in resposta.get_data(as_text=True)


def _registrar(client, doacao, receber=None, cancelar=None, token=None):
    dados = {"token": token or uuid.uuid4().hex, "observacao": ""}
    for di_id, qtd in (receber or {}).items():
        dados[f"receber_{di_id}"] = qtd
    for di_id, qtd in (cancelar or {}).items():
        dados[f"cancelar_{di_id}"] = qtd
    return client.post(f"/admin/doacoes/{doacao.id}", data=dados, follow_redirects=True)


def _doacao_de_5kg(client, evento):
    doar(client, item_por_nome(evento, "Arroz"), 5)
    return db.session.scalar(db.select(Doacao))


def test_registrar_recebimento_parcial(client, login, evento):
    doacao = _doacao_de_5kg(client, evento)
    login()
    di = doacao.itens[0]

    _registrar(client, doacao, receber={di.id: 2})
    db.session.refresh(di)
    assert di.quantidade_recebida == 2
    assert db.session.get(Doacao, doacao.id).status == StatusDoacao.PARCIAL

    _registrar(client, doacao, receber={di.id: 3})
    db.session.refresh(di)
    assert di.quantidade_recebida == 5
    assert db.session.get(Doacao, doacao.id).status == StatusDoacao.RECEBIDA

    # Receber não altera a reserva feita na confirmação
    arroz = item_por_nome(evento, "Arroz")
    db.session.refresh(arroz)
    assert arroz.quantidade_comprometida == 5


def test_recebimento_superior_ao_prometido_e_impedido(client, login, evento):
    doacao = _doacao_de_5kg(client, evento)
    login()
    di = doacao.itens[0]
    resposta = _registrar(client, doacao, receber={di.id: 6})
    assert "ultrapassa o pendente" in resposta.get_data(as_text=True)
    db.session.refresh(di)
    assert di.quantidade_recebida == 0


def test_quantidade_negativa_e_impedida(client, login, evento):
    doacao = _doacao_de_5kg(client, evento)
    login()
    resposta = _registrar(client, doacao, receber={doacao.itens[0].id: -1})
    assert "não podem ser negativas" in resposta.get_data(as_text=True)


def test_mesmo_recebimento_nao_e_registrado_duas_vezes(client, login, evento):
    doacao = _doacao_de_5kg(client, evento)
    login()
    di = doacao.itens[0]
    token = uuid.uuid4().hex
    _registrar(client, doacao, receber={di.id: 2}, token=token)
    resposta = _registrar(client, doacao, receber={di.id: 2}, token=token)
    assert "já foi salvo" in resposta.get_data(as_text=True)
    db.session.refresh(di)
    assert di.quantidade_recebida == 2


def test_cancelar_quantidade_pendente_libera_para_novas_doacoes(client, login, evento):
    doacao = _doacao_de_5kg(client, evento)
    login()
    di = doacao.itens[0]
    _registrar(client, doacao, receber={di.id: 2})

    client.post(f"/admin/doacoes/{doacao.id}/cancelar", data={"token": uuid.uuid4().hex})

    db.session.refresh(di)
    arroz = item_por_nome(evento, "Arroz")
    db.session.refresh(arroz)
    assert di.quantidade_recebida == 2       # o recebido continua contabilizado
    assert di.quantidade_cancelada == 3
    assert arroz.quantidade_comprometida == 2  # apenas os 3 kg voltaram
    assert arroz.quantidade_disponivel == 8
    assert db.session.get(Doacao, doacao.id).status == StatusDoacao.CANCELADA


def test_nao_reduz_necessidade_abaixo_do_comprometido(client, login, evento):
    arroz = item_por_nome(evento, "Arroz")
    doar(client, arroz, 7)
    login()
    resposta = client.post(f"/eventos/gerenciar/{evento.id}/itens/{arroz.id}/editar", data={
        "nome": "Arroz", "quantidade_necessaria": 5, "unidade": "kg",
    })
    assert "não pode ser menor que o já comprometido" in resposta.get_data(as_text=True)


def test_dashboard_diferencia_doacoes_de_itens(client, login, evento):
    from app.services.dashboard import indicadores_gerais

    client.post("/doacoes/carrinho/adicionar",
                data={"item_id": item_por_nome(evento, "Feijão").id, "quantidade": 1})
    doar(client, item_por_nome(evento, "Arroz"), 2)

    ind = indicadores_gerais()
    assert ind["doacoes_total"] == 1          # um registro de doação...
    assert ind["itens_aguardando_entrega"] == 2  # ...com dois itens diferentes
    assert ind["doacoes_pendentes"] == 1
    assert ind["eventos_ativos"] == 1
