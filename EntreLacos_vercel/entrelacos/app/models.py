"""Modelos (tabelas) do EntreLaços, mapeados com SQLAlchemy."""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def agora():
    """Horário local do servidor (o sistema é usado por uma organização em um único fuso)."""
    return datetime.now().replace(microsecond=0)


class StatusEvento:
    ABERTO = "aberto"
    ENCERRADO = "encerrado"
    TODOS = (ABERTO, ENCERRADO)


class StatusDoacao:
    PENDENTE = "pendente"
    PARCIAL = "parcial"
    RECEBIDA = "recebida"
    CANCELADA = "cancelada"
    TODOS = (PENDENTE, PARCIAL, RECEBIDA, CANCELADA)
    ROTULOS = {
        PENDENTE: "Pendente",
        PARCIAL: "Parcialmente recebida",
        RECEBIDA: "Recebida",
        CANCELADA: "Cancelada",
    }


class Administrador(UserMixin, db.Model):
    __tablename__ = "administradores"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True)
    senha_hash = db.Column(db.String(256), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    eventos = db.relationship("Evento", back_populates="administrador")

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def is_active(self):
        return self.ativo


@login_manager.user_loader
def carregar_administrador(admin_id):
    return db.session.get(Administrador, int(admin_id))


class Evento(db.Model):
    __tablename__ = "eventos"
    __table_args__ = (
        db.CheckConstraint("status IN ('aberto', 'encerrado')", name="status_valido"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text)
    data = db.Column(db.Date, nullable=False)
    local = db.Column(db.String(200))
    # Nome único da capa (muda a cada troca de imagem e entra na URL, evitando cache antigo)
    imagem_capa = db.Column(db.String(255), nullable=False)
    # A imagem fica no próprio banco: na Vercel não existe disco permanente para uploads.
    # deferred = só é carregada quando a rota da capa pede, não em toda listagem de eventos.
    imagem_dados = db.deferred(db.Column(db.LargeBinary))
    imagem_tipo = db.Column(db.String(10))
    status = db.Column(db.String(20), nullable=False, default=StatusEvento.ABERTO, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)
    administrador_id = db.Column(
        db.Integer, db.ForeignKey("administradores.id", ondelete="RESTRICT"), nullable=False
    )

    administrador = db.relationship("Administrador", back_populates="eventos")
    itens = db.relationship(
        "Item", back_populates="evento", order_by="Item.nome", cascade="all, delete-orphan"
    )
    doacoes = db.relationship("Doacao", back_populates="evento", order_by="Doacao.criado_em.desc()")

    @property
    def aberto(self):
        return self.status == StatusEvento.ABERTO

    @property
    def itens_ativos(self):
        return [item for item in self.itens if item.ativo]


class Item(db.Model):
    __tablename__ = "itens"
    __table_args__ = (
        db.CheckConstraint("quantidade_necessaria > 0", name="necessaria_positiva"),
        db.CheckConstraint("quantidade_comprometida >= 0", name="comprometida_nao_negativa"),
        db.CheckConstraint(
            "quantidade_comprometida <= quantidade_necessaria", name="comprometida_limite"
        ),
        db.UniqueConstraint("evento_id", "nome", name="uq_itens_evento_nome"),
    )

    id = db.Column(db.Integer, primary_key=True)
    evento_id = db.Column(
        db.Integer, db.ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.String(255))
    quantidade_necessaria = db.Column(db.Integer, nullable=False)
    # Soma reservada por doações (inclui o que já foi recebido; exclui cancelamentos)
    quantidade_comprometida = db.Column(db.Integer, nullable=False, default=0)
    unidade = db.Column(db.String(30), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    evento = db.relationship("Evento", back_populates="itens")
    doacao_itens = db.relationship("DoacaoItem", back_populates="item")

    @property
    def quantidade_disponivel(self):
        return max(self.quantidade_necessaria - self.quantidade_comprometida, 0)

    @property
    def quantidade_recebida(self):
        return sum(di.quantidade_recebida for di in self.doacao_itens)

    @property
    def percentual_comprometido(self):
        return round(100 * self.quantidade_comprometida / self.quantidade_necessaria)

    @property
    def percentual_recebido(self):
        return round(100 * self.quantidade_recebida / self.quantidade_necessaria)


class Doador(db.Model):
    __tablename__ = "doadores"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, index=True)
    telefone = db.Column(db.String(15), nullable=False, unique=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    doacoes = db.relationship("Doacao", back_populates="doador")


class Doacao(db.Model):
    __tablename__ = "doacoes"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pendente', 'parcial', 'recebida', 'cancelada')", name="status_valido"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    evento_id = db.Column(
        db.Integer, db.ForeignKey("eventos.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    doador_id = db.Column(
        db.Integer, db.ForeignKey("doadores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Nome informado no momento da doação (o cadastro do doador pode mudar depois)
    nome_informado = db.Column(db.String(150), nullable=False)
    observacao = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default=StatusDoacao.PENDENTE, index=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora)

    evento = db.relationship("Evento", back_populates="doacoes")
    doador = db.relationship("Doador", back_populates="doacoes")
    itens = db.relationship(
        "DoacaoItem", back_populates="doacao", cascade="all, delete-orphan",
        order_by="DoacaoItem.id",
    )
    entregas = db.relationship(
        "Entrega", back_populates="doacao", order_by="Entrega.registrado_em.desc()"
    )

    @property
    def rotulo_status(self):
        return StatusDoacao.ROTULOS[self.status]

    @property
    def codigo(self):
        return f"EL-{self.id:05d}"

    def recalcular_status(self):
        """Define a situação da doação a partir das quantidades de cada item."""
        self.status = calcular_status(
            sum(i.quantidade_prometida for i in self.itens),
            sum(i.quantidade_recebida for i in self.itens),
            sum(i.quantidade_cancelada for i in self.itens),
        )
        return self.status


class DoacaoItem(db.Model):
    __tablename__ = "doacao_itens"
    __table_args__ = (
        db.CheckConstraint("quantidade_prometida > 0", name="prometida_positiva"),
        db.CheckConstraint("quantidade_recebida >= 0", name="recebida_nao_negativa"),
        db.CheckConstraint("quantidade_cancelada >= 0", name="cancelada_nao_negativa"),
        db.CheckConstraint(
            "quantidade_recebida + quantidade_cancelada <= quantidade_prometida",
            name="limite_prometido",
        ),
        db.UniqueConstraint("doacao_id", "item_id", name="uq_doacao_itens_doacao_item"),
    )

    id = db.Column(db.Integer, primary_key=True)
    doacao_id = db.Column(
        db.Integer, db.ForeignKey("doacoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id = db.Column(
        db.Integer, db.ForeignKey("itens.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantidade_prometida = db.Column(db.Integer, nullable=False)
    quantidade_recebida = db.Column(db.Integer, nullable=False, default=0)
    quantidade_cancelada = db.Column(db.Integer, nullable=False, default=0)

    doacao = db.relationship("Doacao", back_populates="itens")
    item = db.relationship("Item", back_populates="doacao_itens")
    recebimentos = db.relationship("Recebimento", back_populates="doacao_item")

    @property
    def quantidade_pendente(self):
        return self.quantidade_prometida - self.quantidade_recebida - self.quantidade_cancelada

    @property
    def status(self):
        return calcular_status(
            self.quantidade_prometida, self.quantidade_recebida, self.quantidade_cancelada
        )

    @property
    def rotulo_status(self):
        return StatusDoacao.ROTULOS[self.status]


class Entrega(db.Model):
    """Registro de uma entrega (lote) feita pelo doador e conferida pelo organizador."""

    __tablename__ = "entregas"

    id = db.Column(db.Integer, primary_key=True)
    doacao_id = db.Column(
        db.Integer, db.ForeignKey("doacoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    administrador_id = db.Column(
        db.Integer, db.ForeignKey("administradores.id", ondelete="RESTRICT"), nullable=False
    )
    # Token único gerado no formulário: impede registrar o mesmo envio duas vezes
    token = db.Column(db.String(36), nullable=False, unique=True)
    tipo = db.Column(db.String(20), nullable=False, default="recebimento")
    observacao = db.Column(db.String(255))
    registrado_em = db.Column(db.DateTime, nullable=False, default=agora)

    doacao = db.relationship("Doacao", back_populates="entregas")
    administrador = db.relationship("Administrador")
    recebimentos = db.relationship(
        "Recebimento", back_populates="entrega", cascade="all, delete-orphan"
    )


class Recebimento(db.Model):
    """Quantidade de um item registrada em uma entrega (recebida ou cancelada)."""

    __tablename__ = "recebimentos"
    __table_args__ = (
        db.CheckConstraint("quantidade_recebida >= 0", name="recebida_nao_negativa"),
        db.CheckConstraint("quantidade_cancelada >= 0", name="cancelada_nao_negativa"),
        db.CheckConstraint(
            "quantidade_recebida + quantidade_cancelada > 0", name="movimento_positivo"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    entrega_id = db.Column(
        db.Integer, db.ForeignKey("entregas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doacao_item_id = db.Column(
        db.Integer, db.ForeignKey("doacao_itens.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantidade_recebida = db.Column(db.Integer, nullable=False, default=0)
    quantidade_cancelada = db.Column(db.Integer, nullable=False, default=0)

    entrega = db.relationship("Entrega", back_populates="recebimentos")
    doacao_item = db.relationship("DoacaoItem", back_populates="recebimentos")


def calcular_status(prometido, recebido, cancelado):
    pendente = prometido - recebido - cancelado
    if pendente > 0:
        return StatusDoacao.PARCIAL if recebido > 0 else StatusDoacao.PENDENTE
    if cancelado > 0:
        return StatusDoacao.CANCELADA
    return StatusDoacao.RECEBIDA
