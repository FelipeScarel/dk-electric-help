import hashlib
import secrets
from datetime import datetime, timedelta

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, event

db = SQLAlchemy()


def generate_hash_id():
    raw = secrets.token_hex(6) + str(datetime.utcnow().timestamp())
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(200), nullable=False)
    empresa = db.Column(db.String(200))
    telefone = db.Column(db.String(30), nullable=False)
    cep = db.Column(db.String(10))
    endereco = db.Column(db.String(300), nullable=False)
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(150))
    cidade = db.Column(db.String(150), nullable=False)
    estado = db.Column(db.String(2))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    orcamentos = db.relationship("Orcamento", back_populates="cliente", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "empresa": self.empresa,
            "telefone": self.telefone,
            "cep": self.cep,
            "endereco": self.endereco,
            "numero": self.numero,
            "complemento": self.complemento,
            "bairro": self.bairro,
            "cidade": self.cidade,
            "estado": self.estado,
        }


class Orcamento(db.Model):
    __tablename__ = "orcamentos"
    __table_args__ = (
        Index("ix_orcamentos_hash", "hash_id"),
        Index("ix_orcamentos_status", "status"),
        CheckConstraint("status IN ('PENDENTE', 'APROVADO_PELO_CLIENTE', 'AGENDADO', 'CONCLUIDO', 'CANCELADO')"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    hash_id = db.Column(db.String(12), unique=True, nullable=False, default=generate_hash_id)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    data_emissao = db.Column(db.DateTime, default=datetime.utcnow)
    data_validade = db.Column(db.DateTime, nullable=False)
    valor_total = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default="PENDENTE")
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="orcamentos")
    itens = db.relationship("ItemOrcamento", back_populates="orcamento", cascade="all, delete-orphan")
    agendamento = db.relationship("Agendamento", back_populates="orcamento", uselist=False, cascade="all, delete-orphan")

    def recalcular_total(self):
        self.valor_total = sum(item.valor_total for item in self.itens)

    def to_dict(self):
        return {
            "id": self.id,
            "hash_id": self.hash_id,
            "cliente": self.cliente.to_dict(),
            "data_emissao": self.data_emissao.isoformat(),
            "data_validade": self.data_validade.isoformat(),
            "valor_total": self.valor_total,
            "status": self.status,
            "itens": [item.to_dict() for item in self.itens],
        }


class ItemOrcamento(db.Model):
    __tablename__ = "itens_orcamento"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey("orcamentos.id"), nullable=False)
    item = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.String(500), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    valor_unitario = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)

    orcamento = db.relationship("Orcamento", back_populates="itens")

    def to_dict(self):
        return {
            "id": self.id,
            "item": self.item,
            "descricao": self.descricao,
            "quantidade": self.quantidade,
            "valor_unitario": self.valor_unitario,
            "valor_total": self.valor_total,
        }


class Agendamento(db.Model):
    __tablename__ = "agendamentos"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey("orcamentos.id"), unique=True, nullable=False)
    data_agendada = db.Column(db.DateTime, nullable=False)
    periodo = db.Column(db.String(20), nullable=False)
    observacoes_cliente = db.Column(db.Text)
    confirmado_em = db.Column(db.DateTime, default=datetime.utcnow)

    orcamento = db.relationship("Orcamento", back_populates="agendamento")

    def to_dict(self):
        return {
            "id": self.id,
            "data_agendada": self.data_agendada.isoformat(),
            "periodo": self.periodo,
            "confirmado_em": self.confirmado_em.isoformat(),
        }


class SlotHorario(db.Model):
    __tablename__ = "slots_horario"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fim = db.Column(db.Time, nullable=False)
    disponivel = db.Column(db.Boolean, default=True)
    agendamento_id = db.Column(db.Integer, db.ForeignKey("agendamentos.id"), nullable=True)

    __table_args__ = (
        Index("ix_slots_data", "data"),
        UniqueConstraint("data", "hora_inicio", name="uq_slot_horario"),
    )


class NotificationLog(db.Model):
    """Registro de envio de notificacoes WhatsApp."""
    __tablename__ = "notification_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    agendamento_id = db.Column(db.Integer, db.ForeignKey("agendamentos.id"), nullable=True)
    phone_to = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending, sent, failed
    message_body = db.Column(db.Text)
    response = db.Column(db.Text)
    attempts = db.Column(db.Integer, default=1)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _seed_slots(app)


def _seed_slots(app):
    if SlotHorario.query.first() is not None:
        return
    hoje = datetime.utcnow().date()
    periodos = [
        ("08:00", "09:30"),
        ("09:30", "11:00"),
        ("11:00", "12:30"),
        ("13:30", "15:00"),
        ("15:00", "16:30"),
        ("16:30", "18:00"),
    ]
    slots = []
    for dia_offset in range(1, 61):
        dia = hoje + timedelta(days=dia_offset)
        if dia.weekday() >= 5:
            continue
        for hi, hf in periodos:
            slots.append(
                SlotHorario(
                    data=dia,
                    hora_inicio=datetime.strptime(hi, "%H:%M").time(),
                    hora_fim=datetime.strptime(hf, "%H:%M").time(),
                )
            )
    db.session.bulk_save_objects(slots)
    db.session.commit()
