"""Formulários do sistema, validados no servidor com Flask-WTF / WTForms."""
import uuid
from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired, FileSize
from wtforms import (
    BooleanField, DateField, EmailField, HiddenField, IntegerField, PasswordField,
    RadioField, SelectField, StringField, SubmitField, TextAreaField,
)
from wtforms.validators import (
    DataRequired, Email, InputRequired, Length, NumberRange, Optional, ValidationError,
)

from .models import StatusEvento
from .utils import telefone_valido

EXTENSOES_IMAGEM = ["jpg", "jpeg", "png", "webp"]
TAMANHO_MAX_IMAGEM = 3 * 1024 * 1024


def validar_telefone(_form, campo):
    if not telefone_valido(campo.data):
        raise ValidationError("Informe um telefone válido com DDD, ex.: (27) 99999-1234.")


def validar_nome_completo(_form, campo):
    partes = (campo.data or "").split()
    if len(partes) < 2:
        raise ValidationError("Informe nome e sobrenome.")
    if any(ch.isdigit() for ch in campo.data):
        raise ValidationError("O nome não pode conter números.")


class LoginForm(FlaskForm):
    email = EmailField("E-mail", validators=[
        DataRequired("Informe o e-mail."), Email("Informe um e-mail válido."), Length(max=160),
    ])
    senha = PasswordField("Senha", validators=[DataRequired("Informe a senha.")])
    lembrar = BooleanField("Manter conectado")
    enviar = SubmitField("Entrar")


class EventoForm(FlaskForm):
    nome = StringField("Nome do evento", validators=[
        DataRequired("Informe o nome do evento."), Length(min=3, max=150),
    ])
    descricao = TextAreaField("Descrição", validators=[Optional(), Length(max=2000)])
    data = DateField("Data", validators=[DataRequired("Informe uma data válida.")])
    local = StringField("Local", validators=[Optional(), Length(max=200)])
    imagem_capa = FileField("Imagem de capa", validators=[
        FileAllowed(EXTENSOES_IMAGEM, "Envie uma imagem JPG, PNG ou WEBP."),
        FileSize(max_size=TAMANHO_MAX_IMAGEM, message="A imagem deve ter no máximo 3 MB."),
    ])
    status = SelectField("Status", choices=[
        (StatusEvento.ABERTO, "Aberto para doações"),
        (StatusEvento.ENCERRADO, "Encerrado"),
    ], validators=[DataRequired()])
    enviar = SubmitField("Salvar evento")

    def validate_data(self, campo):
        # Um evento novo e aberto não pode ser marcado para uma data que já passou
        if campo.data and self.status.data == StatusEvento.ABERTO and campo.data < date.today() \
                and not getattr(self, "_edicao", False):
            raise ValidationError("A data do evento não pode estar no passado.")
        if campo.data and campo.data.year > date.today().year + 5:
            raise ValidationError("Informe uma data dentro dos próximos 5 anos.")


class NovoEventoForm(EventoForm):
    imagem_capa = FileField("Imagem de capa", validators=[
        FileRequired("Envie uma imagem de capa."),
        FileAllowed(EXTENSOES_IMAGEM, "Envie uma imagem JPG, PNG ou WEBP."),
        FileSize(max_size=TAMANHO_MAX_IMAGEM, message="A imagem deve ter no máximo 3 MB."),
    ])


class ItemForm(FlaskForm):
    nome = StringField("Nome do item", validators=[
        DataRequired("Informe o nome do item."), Length(min=2, max=120),
    ])
    descricao = StringField("Descrição", validators=[Optional(), Length(max=255)])
    quantidade_necessaria = IntegerField("Quantidade necessária", validators=[
        InputRequired("Informe a quantidade."),
        NumberRange(min=1, max=100000, message="A quantidade deve ser maior que zero."),
    ])
    unidade = StringField("Unidade de medida", validators=[
        DataRequired("Informe a unidade (ex.: kg, litros, pacotes)."), Length(max=30),
    ])
    enviar = SubmitField("Salvar item")


class AdicionarCarrinhoForm(FlaskForm):
    item_id = HiddenField(validators=[DataRequired()])
    quantidade = IntegerField("Quantidade", validators=[
        InputRequired("Informe a quantidade."),
        NumberRange(min=1, message="A quantidade deve ser maior que zero."),
    ])


class AlterarCarrinhoForm(FlaskForm):
    quantidade = IntegerField("Quantidade", validators=[
        InputRequired(), NumberRange(min=0, max=100000, message="Quantidade inválida."),
    ])


class AcaoSimplesForm(FlaskForm):
    """Formulário vazio usado em botões (remover, esvaziar, desativar) para ter CSRF."""


class ConfirmacaoDoacaoForm(FlaskForm):
    nome = StringField("Nome completo", validators=[
        DataRequired("Informe seu nome completo."), Length(min=5, max=150),
        validar_nome_completo,
    ])
    telefone = StringField("Telefone (com DDD)", validators=[
        DataRequired("Informe seu telefone."), validar_telefone,
    ])
    observacao = TextAreaField("Observação (opcional)", validators=[
        Optional(), Length(max=500, message="Use no máximo 500 caracteres."),
    ])
    enviar = SubmitField("Confirmar doação")


class PesquisaDoacaoForm(FlaskForm):
    tipo = RadioField("Pesquisar por", choices=[("nome", "Nome"), ("telefone", "Telefone")],
                      default="nome", validators=[DataRequired()])
    termo = StringField("Nome ou telefone", validators=[DataRequired("Digite algo para pesquisar.")])
    enviar = SubmitField("Pesquisar")

    def validate_termo(self, campo):
        if self.tipo.data == "telefone":
            if not telefone_valido(campo.data):
                raise ValidationError("Informe o telefone completo com DDD.")
        elif len((campo.data or "").strip()) < 3:
            raise ValidationError("Digite ao menos 3 letras do nome.")


class AcompanharDoacaoForm(PesquisaDoacaoForm):
    """Pesquisa geral: permite escolher um evento ou procurar em todos."""
    evento = SelectField("Evento", coerce=int, default=0, validators=[Optional()])


class RecebimentoForm(FlaskForm):
    """Os campos de quantidade por item são lidos dinamicamente na rota."""
    token = HiddenField(validators=[DataRequired()])
    observacao = StringField("Observação da entrega", validators=[Optional(), Length(max=255)])
    enviar = SubmitField("Registrar")

    def gerar_token(self):
        self.token.data = uuid.uuid4().hex
        return self


class FiltroDoacoesForm(FlaskForm):
    class Meta:
        csrf = False

    evento = SelectField("Evento", coerce=int, validators=[Optional()])
    status = SelectField("Situação", validators=[Optional()])
    busca = StringField("Doador", validators=[Optional(), Length(max=100)])
