"""Páginas públicas, carrinho e confirmação de doação."""
from app.extensions import db
from app.models import Doacao, Doador, StatusEvento

from conftest import doar, item_por_nome


def test_pagina_inicial_lista_eventos_abertos(client, evento):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert "Almoço solidário".encode() in resposta.data


def test_evento_encerrado_nao_aparece_entre_os_abertos(client, evento):
    evento.status = StatusEvento.ENCERRADO
    db.session.commit()
    html = client.get("/").get_data(as_text=True)
    assert "Eventos recebendo doações" in html
    assert "Eventos encerrados" in html
    assert "Ver itens e doar" not in html


def test_consultar_evento_existente_exibe_detalhes_e_itens(client, evento):
    resposta = client.get(f"/eventos/{evento.id}")
    html = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert "Almoço solidário" in html
    assert "Arroz" in html and "Feijão" in html


def test_evento_inexistente_retorna_404(client, app):
    assert client.get("/eventos/999").status_code == 404


def test_confirmar_doacao_valida_registra_e_reserva(client, evento):
    arroz = item_por_nome(evento, "Arroz")
    resposta = doar(client, arroz, 4)

    assert "Obrigado, Maria" in resposta.get_data(as_text=True)
    doacao = db.session.scalar(db.select(Doacao))
    assert doacao is not None
    assert doacao.itens[0].quantidade_prometida == 4
    assert doacao.doador.telefone == "27999991234"
    db.session.refresh(arroz)
    assert arroz.quantidade_comprometida == 4
    assert arroz.quantidade_disponivel == 6


def test_confirmar_doacao_sem_nome_e_rejeitada(client, evento):
    arroz = item_por_nome(evento, "Arroz")
    resposta = doar(client, arroz, 2, nome="")
    assert "Informe seu nome completo" in resposta.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(Doacao.id))) == 0


def test_telefone_invalido_e_rejeitado(client, evento):
    arroz = item_por_nome(evento, "Arroz")
    resposta = doar(client, arroz, 2, telefone="12345")
    assert "Informe um telefone válido" in resposta.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(Doador.id))) == 0


def test_nao_permite_adicionar_mais_que_o_disponivel(client, evento):
    arroz = item_por_nome(evento, "Arroz")
    resposta = client.post("/doacoes/carrinho/adicionar",
                           data={"item_id": arroz.id, "quantidade": 11}, follow_redirects=True)
    assert "Só restam 10 kg" in resposta.get_data(as_text=True)


def test_confirmacao_recusada_se_outro_doador_reservou_antes(client, app, evento):
    """Duas pessoas com o mesmo item no carrinho: a segunda confirmação é recusada inteira."""
    arroz = item_por_nome(evento, "Arroz")
    feijao = item_por_nome(evento, "Feijão")

    outro = app.test_client()
    outro.post("/doacoes/carrinho/adicionar", data={"item_id": arroz.id, "quantidade": 8})

    client.post("/doacoes/carrinho/adicionar", data={"item_id": feijao.id, "quantidade": 2})
    doar(client, arroz, 5, nome="Ana Lima", telefone="27988887777")

    resposta = outro.post("/doacoes/confirmar", data={
        "nome": "João Pereira", "telefone": "27977776666",
    }, follow_redirects=True)
    assert "não têm mais a quantidade escolhida" in resposta.get_data(as_text=True)

    db.session.refresh(arroz)
    assert arroz.quantidade_comprometida == 5  # nada do segundo doador foi gravado
    assert db.session.scalar(db.select(db.func.count(Doacao.id))) == 1


def test_evento_encerrado_impede_nova_contribuicao(client, evento):
    arroz = item_por_nome(evento, "Arroz")
    evento.status = StatusEvento.ENCERRADO
    db.session.commit()

    resposta = client.post("/doacoes/carrinho/adicionar",
                           data={"item_id": arroz.id, "quantidade": 1}, follow_redirects=True)
    assert "não está mais recebendo doações" in resposta.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(Doacao.id))) == 0


def test_carrinho_pertence_a_um_unico_evento(client, admin, evento):
    from datetime import date, timedelta
    from app.models import Evento, Item

    outro = Evento(nome="Outro evento", data=date.today() + timedelta(days=5),
                   imagem_capa="x.png", administrador=admin)
    outro.itens.append(Item(nome="Leite", quantidade_necessaria=5, unidade="litros"))
    db.session.add(outro)
    db.session.commit()

    client.post("/doacoes/carrinho/adicionar",
                data={"item_id": item_por_nome(evento, "Arroz").id, "quantidade": 1})
    resposta = client.post("/doacoes/carrinho/adicionar",
                           data={"item_id": outro.itens[0].id, "quantidade": 1},
                           follow_redirects=True)
    assert "já tem itens de outro evento" in resposta.get_data(as_text=True)


def test_consulta_por_telefone_nao_exibe_o_numero(client, evento):
    doar(client, item_por_nome(evento, "Arroz"), 3)
    resposta = client.post(f"/doacoes/evento/{evento.id}/consulta",
                           data={"tipo": "telefone", "termo": "(27) 99999-1234"})
    html = resposta.get_data(as_text=True)
    assert "Maria Souza" in html
    assert "99999" not in html and "27999991234" not in html


def test_pagina_inicial_deixa_claro_que_doar_nao_exige_login(client, evento):
    html = client.get("/").get_data(as_text=True)
    assert "Sem cadastro e sem login" in html
    assert "Entrar como organizador" in html
    assert "Acompanhar doação" in html


def test_acompanhar_doacao_em_todos_os_eventos(client, evento):
    doar(client, item_por_nome(evento, "Arroz"), 2)
    html = client.post("/doacoes/acompanhar", data={
        "evento": 0, "tipo": "telefone", "termo": "27 99999-1234",
    }).get_data(as_text=True)
    assert "Maria Souza" in html
    assert "Almoço solidário" in html  # mostra o evento de cada doação
    assert "99999" not in html.replace("(27) 99999-1234", "")  # só o placeholder


def test_acompanhar_doacao_filtrando_outro_evento_nao_encontra(client, admin, evento):
    from datetime import date, timedelta
    from app.models import Evento

    outro = Evento(nome="Outro", data=date.today() + timedelta(days=3),
                   imagem_capa="x.png", administrador=admin)
    db.session.add(outro)
    db.session.commit()
    doar(client, item_por_nome(evento, "Arroz"), 2)

    html = client.post("/doacoes/acompanhar", data={
        "evento": outro.id, "tipo": "nome", "termo": "Maria",
    }).get_data(as_text=True)
    assert "Nenhuma doação encontrada" in html


def test_consulta_por_nome_mostra_situacao(client, evento):
    doar(client, item_por_nome(evento, "Arroz"), 3, obs="Observação privada")
    html = client.post(f"/doacoes/evento/{evento.id}/consulta",
                       data={"tipo": "nome", "termo": "maria"}).get_data(as_text=True)
    assert "Maria Souza" in html
    assert "Pendente" in html
    assert "Observação privada" not in html
