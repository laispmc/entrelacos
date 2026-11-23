"""Comandos de terminal: `flask criar-admin`, `flask redefinir-senha` e `flask popular`."""
import getpass
import math
import os
import struct
import zlib
from datetime import date, timedelta

import click
from email_validator import EmailNotValidError, validate_email
from flask import current_app

from .extensions import db
from .models import Administrador, Evento, Item, StatusEvento


def registrar_comandos(app):
    app.cli.add_command(criar_admin)
    app.cli.add_command(redefinir_senha)
    app.cli.add_command(popular)


def _validar_email(email):
    """Mesma validação usada no formulário de login. Retorna None se for inválido."""
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as erro:
        click.echo(f"E-mail inválido: {erro}")
        return None


def _pedir_senha():
    """Pede a senha duas vezes (sem mostrar na tela). Retorna None se não conferir."""
    senha = os.environ.get("ADMIN_SENHA")
    if senha:
        return senha if len(senha) >= 8 else None
    senha = getpass.getpass("Senha (mín. 8 caracteres, não aparece ao digitar): ")
    if len(senha) < 8:
        click.echo("A senha precisa ter pelo menos 8 caracteres.")
        return None
    if getpass.getpass("Repita a senha: ") != senha:
        click.echo("As senhas não conferem. Nada foi alterado; tente de novo.")
        return None
    return senha


@click.command("criar-admin")
@click.option("--nome", prompt="Nome")
@click.option("--email", prompt="E-mail")
def criar_admin(nome, email):
    """Cria um administrador (a senha é pedida duas vezes, sem aparecer na tela)."""
    email = _validar_email(email)
    if email is None:
        return
    if db.session.scalar(db.select(Administrador).filter_by(email=email)):
        click.echo("Já existe um administrador com esse e-mail. "
                   "Para trocar a senha use: flask --app run redefinir-senha")
        return
    senha = _pedir_senha()
    if senha is None:
        return
    admin = Administrador(nome=nome.strip(), email=email)
    admin.definir_senha(senha)
    db.session.add(admin)
    db.session.commit()
    click.echo(f"Administrador {email} criado.")


@click.command("redefinir-senha")
@click.option("--email", prompt="E-mail do administrador")
def redefinir_senha(email):
    """Troca a senha de um administrador existente."""
    email = _validar_email(email)
    if email is None:
        return
    admin = db.session.scalar(db.select(Administrador).filter_by(email=email))
    if admin is None:
        click.echo("Nenhum administrador com esse e-mail.")
        return
    senha = _pedir_senha()
    if senha is None:
        return
    admin.definir_senha(senha)
    admin.ativo = True
    db.session.commit()
    current_app.logger.info("Senha redefinida pelo terminal para o administrador %s", admin.id)
    click.echo(f"Senha de {email} redefinida. Já pode entrar em /admin/login.")


@click.command("popular")
def popular():
    """Cadastra eventos de exemplo para demonstração."""
    admin = db.session.scalar(db.select(Administrador).order_by(Administrador.id))
    if admin is None:
        click.echo("Crie um administrador antes: flask criar-admin")
        return
    if db.session.scalar(db.select(Evento.id).limit(1)):
        click.echo("O banco já possui eventos. Nada foi alterado.")
        return

    hoje = date.today()
    exemplos = [
        {
            "nome": "Almoço solidário de Natal",
            "descricao": "Almoço para 120 famílias atendidas pela pastoral, "
                         "com entrega de cestas ao final.",
            "data": hoje + timedelta(days=30), "local": "Salão paroquial São José",
            "cores": ((176, 74, 46), (232, 177, 120)),
            "itens": [("Arroz", "Tipo 1", 60, "kg"), ("Feijão", "Carioca", 40, "kg"),
                      ("Óleo de soja", None, 24, "garrafas"),
                      ("Frango congelado", "Entregar no dia anterior", 50, "kg"),
                      ("Refrigerante 2L", None, 40, "unidades"),
                      ("Pratos descartáveis", "Pacote com 10", 30, "pacotes")],
        },
        {
            "nome": "Campanha do agasalho",
            "descricao": "Arrecadação de roupas de frio e cobertores para a "
                         "população em situação de rua.",
            "data": hoje + timedelta(days=18), "local": "Centro comunitário da Vila Rubim",
            "cores": ((47, 82, 92), (140, 178, 170)),
            "itens": [("Cobertor de casal", None, 80, "unidades"),
                      ("Meias", "Pares novos", 150, "pares"),
                      ("Casaco adulto", "Em bom estado", 60, "unidades"),
                      ("Gorro", None, 40, "unidades")],
        },
        {
            "nome": "Retiro de jovens",
            "descricao": "Fim de semana de convivência para 45 jovens da comunidade.",
            "data": hoje + timedelta(days=45), "local": "Sítio Boa Esperança",
            "cores": ((96, 108, 56), (214, 196, 128)),
            "itens": [("Pão de forma", None, 30, "pacotes"), ("Café", "500 g", 10, "pacotes"),
                      ("Leite", None, 48, "litros"), ("Frutas", "Variadas", 20, "kg"),
                      ("Papel higiênico", "Fardo com 12", 6, "fardos")],
        },
    ]

    for indice, dados in enumerate(exemplos, start=1):
        evento = Evento(nome=dados["nome"], descricao=dados["descricao"], data=dados["data"],
                        local=dados["local"], imagem_capa=f"exemplo-{indice}.png",
                        imagem_dados=_gerar_capa(*dados["cores"], semente=indice),
                        imagem_tipo="png", status=StatusEvento.ABERTO, administrador=admin)
        for nome, descricao, qtd, unidade in dados["itens"]:
            evento.itens.append(Item(nome=nome, descricao=descricao,
                                     quantidade_necessaria=qtd, unidade=unidade))
        db.session.add(evento)
    db.session.commit()
    click.echo(f"{len(exemplos)} eventos de exemplo cadastrados.")


def _gerar_capa(cor_a, cor_b, semente=1, largura=960, altura=540):
    """Gera os bytes de uma imagem PNG simples (gradiente com ondas) sem bibliotecas externas."""
    linhas = bytearray()
    for y in range(altura):
        linhas.append(0)
        for x in range(largura):
            onda = math.sin((x / largura) * math.pi * (2 + semente) + y / 70) * 0.5 + 0.5
            t = min(max(0.65 * (y / altura) + 0.35 * onda, 0), 1)
            linhas.extend(int(a + (b - a) * t) for a, b in zip(cor_a, cor_b))

    def bloco(tipo, dados):
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))

    cabecalho = struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", cabecalho)
            + bloco(b"IDAT", zlib.compress(bytes(linhas), 9)) + bloco(b"IEND", b""))
