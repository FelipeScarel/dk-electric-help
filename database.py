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
    total_materiais = db.Column(db.Float, default=0.0)
    total_mao_obra = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default="PENDENTE")
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="orcamentos")
    itens = db.relationship("ItemOrcamento", back_populates="orcamento", cascade="all, delete-orphan")
    agendamento = db.relationship("Agendamento", back_populates="orcamento", uselist=False, cascade="all, delete-orphan")

    def recalcular_total(self):
        self.total_materiais = sum(item.valor_total_material for item in self.itens)
        self.total_mao_obra = sum(item.valor_total_mao_obra for item in self.itens)
        self.valor_total = self.total_materiais + self.total_mao_obra

    def to_dict(self):
        return {
            "id": self.id,
            "hash_id": self.hash_id,
            "cliente": self.cliente.to_dict(),
            "data_emissao": self.data_emissao.isoformat(),
            "data_validade": self.data_validade.isoformat(),
            "valor_total": self.valor_total,
            "total_materiais": self.total_materiais,
            "total_mao_obra": self.total_mao_obra,
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
    valor_material = db.Column(db.Float, nullable=False, default=0.0)
    valor_mao_obra = db.Column(db.Float, nullable=False, default=0.0)
    valor_unitario = db.Column(db.Float, nullable=False, default=0.0)  # legacy — mantido para compatibilidade
    valor_total = db.Column(db.Float, nullable=False, default=0.0)
    valor_total_material = db.Column(db.Float, nullable=False, default=0.0)
    valor_total_mao_obra = db.Column(db.Float, nullable=False, default=0.0)

    orcamento = db.relationship("Orcamento", back_populates="itens")

    def to_dict(self):
        return {
            "id": self.id,
            "item": self.item,
            "descricao": self.descricao,
            "quantidade": self.quantidade,
            "valor_material": self.valor_material,
            "valor_mao_obra": self.valor_mao_obra,
            "valor_unitario": self.valor_unitario,
            "valor_total": self.valor_total,
            "valor_total_material": self.valor_total_material,
            "valor_total_mao_obra": self.valor_total_mao_obra,
        }


class Agendamento(db.Model):
    __tablename__ = "agendamentos"
    __table_args__ = (
        CheckConstraint("status IN ('CONFIRMADO', 'REAGENDADO', 'CANCELADO', 'MANUAL')"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey("orcamentos.id"), unique=True, nullable=False)
    data_agendada = db.Column(db.DateTime, nullable=False)
    periodo = db.Column(db.String(20), nullable=False)
    observacoes_cliente = db.Column(db.Text)
    confirmado_em = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="CONFIRMADO")
    reagendado_de = db.Column(db.Integer, db.ForeignKey("agendamentos.id"), nullable=True)
    motivo_cancelamento = db.Column(db.Text)
    criado_por_admin = db.Column(db.Boolean, default=False)

    orcamento = db.relationship("Orcamento", back_populates="agendamento")
    reagendamento_origem = db.relationship("Agendamento", remote_side=[id], uselist=True,
                                            foreign_keys=[reagendado_de],
                                            backref=db.backref("reagendado_para", remote_side=[reagendado_de], uselist=False))

    def to_dict(self):
        return {
            "id": self.id,
            "data_agendada": self.data_agendada.isoformat(),
            "periodo": self.periodo,
            "confirmado_em": self.confirmado_em.isoformat(),
            "status": self.status,
            "criado_por_admin": self.criado_por_admin,
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


class BloqueioAgenda(db.Model):
    """Registra dias/horarios bloqueados manualmente pelo administrador."""
    __tablename__ = "bloqueios_agenda"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data = db.Column(db.Date, nullable=False, index=True)
    horario = db.Column(db.Time, nullable=True)  # NULL = dia inteiro bloqueado
    status_bloqueio = db.Column(db.String(20), default="BLOQUEADO")  # BLOQUEADO, LIBERADO
    motivo_bloqueio = db.Column(db.Text)
    admin_responsavel = db.Column(db.String(200))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_bloqueios_data", "data"),
        Index("ix_bloqueios_status", "status_bloqueio"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "data": self.data.isoformat(),
            "horario": self.horario.strftime("%H:%M") if self.horario else None,
            "status_bloqueio": self.status_bloqueio,
            "motivo_bloqueio": self.motivo_bloqueio,
            "admin_responsavel": self.admin_responsavel,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }


class ConfiguracaoHorario(db.Model):
    """Template semanal de horarios — define quais periodos estao ativos em cada dia da semana."""
    __tablename__ = "configuracao_horarios"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dia_semana = db.Column(db.Integer, nullable=False)  # 0=Seg ... 4=Sex (dias uteis)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fim = db.Column(db.Time, nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("dia_semana", "hora_inicio", name="uq_config_horario"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "dia_semana": self.dia_semana,
            "dia_semana_nome": _dia_semana_nome(self.dia_semana),
            "hora_inicio": self.hora_inicio.strftime("%H:%M"),
            "hora_fim": self.hora_fim.strftime("%H:%M"),
            "ativo": self.ativo,
        }


def _dia_semana_nome(dia):
    nomes = ["Segunda-feira", "Terca-feira", "Quarta-feira",
             "Quinta-feira", "Sexta-feira", "Sabado", "Domingo"]
    return nomes[dia] if 0 <= dia <= 6 else ""


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
        _migrate_db(app)
        _seed_configuracao(app)
        _seed_slots(app)


def _migrate_db(app):
    """Adiciona colunas que nao existem em tabelas ja criadas (SQLite nao faz ALTER automatico)."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)

    # --- agendamentos: status ---
    cols_ag = {c["name"] for c in inspector.get_columns("agendamentos")}
    novas_colunas_ag = {
        "status": "VARCHAR(20) DEFAULT 'CONFIRMADO'",
        "reagendado_de": "INTEGER REFERENCES agendamentos(id)",
        "motivo_cancelamento": "TEXT",
        "criado_por_admin": "BOOLEAN DEFAULT 0",
    }
    with db.engine.connect() as conn:
        for col_name, col_def in novas_colunas_ag.items():
            if col_name not in cols_ag:
                conn.execute(text(f"ALTER TABLE agendamentos ADD COLUMN {col_name} {col_def}"))
                app.logger.info(f"Migracao: coluna '{col_name}' adicionada em agendamentos.")
        conn.commit()


def _seed_configuracao(app):
    """Cria configuracao padrao de horarios se nao existir."""
    if ConfiguracaoHorario.query.first() is not None:
        return
    periodos = [
        ("08:00", "11:30"),
        ("13:00", "18:00"),
    ]
    for dia in range(0, 5):  # Seg a Sex
        for hi, hf in periodos:
            db.session.add(ConfiguracaoHorario(
                dia_semana=dia,
                hora_inicio=datetime.strptime(hi, "%H:%M").time(),
                hora_fim=datetime.strptime(hf, "%H:%M").time(),
            ))
    db.session.commit()
    app.logger.info("Configuracao de horarios padrao criada.")


def _seed_slots(app):
    """Gera slots futuros com base na ConfiguracaoHorario ativa."""
    hoje = datetime.utcnow().date()

    # Remove slots futuros que nao tem agendamento
    SlotHorario.query.filter(
        SlotHorario.data > hoje,
        SlotHorario.agendamento_id == None,
    ).delete()

    configs = ConfiguracaoHorario.query.filter_by(ativo=True).order_by(
        ConfiguracaoHorario.dia_semana, ConfiguracaoHorario.hora_inicio
    ).all()

    if not configs:
        return  # sem config ativa, nao gera slots

    # Agrupa periodos por dia da semana
    periodos_por_dia = {}
    for c in configs:
        periodos_por_dia.setdefault(c.dia_semana, []).append((c.hora_inicio, c.hora_fim))

    # Gera slots para os proximos 90 dias
    slots = []
    for dia_offset in range(1, 91):
        dia = hoje + timedelta(days=dia_offset)
        dw = dia.weekday()
        if dw not in periodos_por_dia:
            continue
        for hi, hf in periodos_por_dia[dw]:
            # Evita duplicatas
            existe = SlotHorario.query.filter_by(data=dia, hora_inicio=hi).first()
            if not existe:
                slots.append(SlotHorario(data=dia, hora_inicio=hi, hora_fim=hf))

    if slots:
        db.session.bulk_save_objects(slots)
        db.session.commit()
        app.logger.info(f"{len(slots)} slots gerados a partir da configuracao.")

