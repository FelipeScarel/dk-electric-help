import os
import traceback
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for
from sqlalchemy import func

from config import Config
from database import (
    Agendamento,
    Cliente,
    ItemOrcamento,
    NotificationLog,
    Orcamento,
    SlotHorario,
    db,
    init_db,
)
from pdf_generator import generate_orcamento_pdf
from whatsapp_service import notify_scheduling


def _utcnow():
    """Retorna datetime UTC naive (sem tzinfo), compativel com o banco SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(Config.PDF_OUTPUT_DIR, exist_ok=True)
    init_db(app)

    @app.errorhandler(500)
    def internal_error(e):
        tb = traceback.format_exc()
        app.logger.error(f"500 ERROR: {tb}")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Erro interno do servidor. Tente novamente."}), 500
        return render_template("erro.html", mensagem="Erro interno do servidor. Tente novamente."), 500

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Nao encontrado."}), 404
        return render_template("erro.html", mensagem="Pagina nao encontrada."), 404

    return app


def _get_base_url():
    """Retorna a URL base correta, respeitando proxy HTTPS (Cloudflare Tunnel, Render, etc)."""
    scheme = request.headers.get("X-Forwarded-Proto", "http")
    host = request.host
    return f"{scheme}://{host}/"


app = create_app()


# ---------------------------------------------------------------------------
# ROTAS DE PAGINAS
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/orcamentos")
def listar_orcamentos():
    orcamentos = (
        Orcamento.query
        .order_by(Orcamento.criado_em.desc())
        .limit(50)
        .all()
    )
    # Estatisticas
    total = Orcamento.query.count()
    valor_total = db.session.query(db.func.sum(Orcamento.valor_total)).scalar() or 0
    pendentes = Orcamento.query.filter_by(status="PENDENTE").count()
    agendados = Orcamento.query.filter_by(status="AGENDADO").count()
    stats = {
        "total": total,
        "valor_total": f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "pendentes": pendentes,
        "agendados": agendados,
    }
    return render_template("orcamentos.html", orcamentos=orcamentos, stats=stats)


# ---------------------------------------------------------------------------
# API: CRIAR ORCAMENTO
# ---------------------------------------------------------------------------

@app.route("/api/orcamentos", methods=["POST"])
def criar_orcamento():
    data = request.get_json(force=True)

    required_client = ["nome", "telefone", "endereco", "cidade"]
    for field in required_client:
        if not data.get(field):
            return jsonify({"error": f"Campo obrigatorio ausente: {field}"}), 400

    if not data.get("itens") or len(data["itens"]) == 0:
        return jsonify({"error": "Adicione pelo menos um item ao orcamento."}), 400

    cliente = Cliente(
        nome=data["nome"].strip(),
        empresa=data.get("empresa", "").strip(),
        telefone=data["telefone"].strip(),
        cep=data.get("cep", "").strip(),
        endereco=data["endereco"].strip(),
        numero=data.get("numero", "").strip(),
        complemento=data.get("complemento", "").strip(),
        bairro=data.get("bairro", "").strip(),
        cidade=data["cidade"].strip(),
        estado=data.get("estado", "").strip().upper(),
    )
    db.session.add(cliente)
    db.session.flush()

    validade_dias = int(data.get("validade_dias", Config.PROPOSAL_VALIDITY_DAYS))
    orcamento = Orcamento(
        cliente_id=cliente.id,
        data_emissao=_utcnow(),
        data_validade=_utcnow() + timedelta(days=validade_dias),
        observacoes=data.get("observacoes", "").strip(),
    )
    db.session.add(orcamento)
    db.session.flush()

    for item_data in data["itens"]:
        qtd = max(1, int(item_data.get("quantidade", 1)))
        vm = max(0.0, float(item_data.get("valor_material", 0)))
        vo = max(0.0, float(item_data.get("valor_mao_obra", 0)))
        vu = vm + vo
        item = ItemOrcamento(
            orcamento_id=orcamento.id,
            item=item_data.get("item", "").strip(),
            descricao=item_data.get("descricao", "").strip(),
            quantidade=qtd,
            valor_material=vm,
            valor_mao_obra=vo,
            valor_unitario=vu,
            valor_total=qtd * vu,
            valor_total_material=qtd * vm,
            valor_total_mao_obra=qtd * vo,
        )
        db.session.add(item)

    orcamento.recalcular_total()
    db.session.commit()

    pdf_path = generate_orcamento_pdf(orcamento, base_url=_get_base_url())

    return jsonify(
        {
            "id": orcamento.id,
            "hash_id": orcamento.hash_id,
            "pdf_url": url_for("download_pdf", hash_id=orcamento.hash_id, _external=True),
            "status": orcamento.status,
        }
    ), 201


# ---------------------------------------------------------------------------
# DOWNLOAD DO PDF
# ---------------------------------------------------------------------------

@app.route("/pdf/<hash_id>")
def download_pdf(hash_id):
    orcamento = Orcamento.query.filter_by(hash_id=hash_id.upper()).first_or_404()
    pdf_filename = f"orcamento_{orcamento.hash_id}.pdf"
    pdf_path = os.path.join(Config.PDF_OUTPUT_DIR, pdf_filename)

    if not os.path.exists(pdf_path):
        pdf_path = generate_orcamento_pdf(orcamento)

    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Orcamento_DK_{orcamento.hash_id}.pdf",
    )


# ---------------------------------------------------------------------------
# ROTA DE VALIDACAO: CLIENTE CLICOU NO BOTAO DO PDF
# ---------------------------------------------------------------------------

@app.route("/validar-orcamento")
def validar_orcamento():
    hash_id = request.args.get("id", "").strip().upper()
    if not hash_id:
        return render_template("erro.html", mensagem="Orcamento nao encontrado."), 404

    orcamento = Orcamento.query.filter_by(hash_id=hash_id).first()
    if not orcamento:
        return render_template("erro.html", mensagem="Orcamento nao encontrado."), 404

    if orcamento.status == "CANCELADO":
        return render_template("erro.html", mensagem="Este orcamento foi cancelado."), 410

    if orcamento.data_validade < _utcnow() and orcamento.status == "PENDENTE":
        return render_template(
            "erro.html",
            mensagem="Este orcamento expirou. Entre em contato pelo telefone (19) 99624-5413 para renova-lo.",
        ), 410

    if orcamento.status == "PENDENTE":
        orcamento.status = "APROVADO_PELO_CLIENTE"
        orcamento.atualizado_em = _utcnow()
        db.session.commit()

    if orcamento.status == "AGENDADO" and orcamento.agendamento:
        return render_template(
            "confirmado.html",
            orcamento=orcamento,
            agendamento=orcamento.agendamento,
        )

    slots_disponiveis = (
        SlotHorario.query
        .filter(
            SlotHorario.disponivel == True,
            SlotHorario.data >= _utcnow().date(),
        )
        .order_by(SlotHorario.data, SlotHorario.hora_inicio)
        .limit(90)
        .all()
    )

    return render_template(
        "agendamento.html",
        orcamento=orcamento,
        slots=slots_disponiveis,
    )


# ---------------------------------------------------------------------------
# API: CONFIRMAR AGENDAMENTO
# ---------------------------------------------------------------------------

@app.route("/api/agendar", methods=["POST"])
def confirmar_agendamento():
    try:
        data = request.get_json(force=True)

        hash_id = data.get("hash_id", "").strip().upper()
        slot_id = data.get("slot_id")

        if not hash_id or not slot_id:
            return jsonify({"error": "Dados incompletos."}), 400

        orcamento = Orcamento.query.filter_by(hash_id=hash_id).first()
        if not orcamento:
            return jsonify({"error": "Orcamento nao encontrado."}), 404

        slot = SlotHorario.query.get(slot_id)
        if not slot or not slot.disponivel:
            return jsonify({"error": "Horario indisponivel. Escolha outro."}), 409

        slot.disponivel = False
        agendamento = Agendamento(
            orcamento_id=orcamento.id,
            data_agendada=datetime.combine(slot.data, slot.hora_inicio),
            periodo=f"{slot.hora_inicio.strftime('%H:%M')} - {slot.hora_fim.strftime('%H:%M')}",
            observacoes_cliente=data.get("observacoes", ""),
        )
        db.session.add(agendamento)
        db.session.flush()
        slot.agendamento_id = agendamento.id
        orcamento.status = "AGENDADO"
        orcamento.atualizado_em = _utcnow()
        db.session.commit()

        # Gerar link WhatsApp com dados do agendamento
        wz_numero = Config.WHATSAPP_NOTIFY.strip()
        wz_msg = notify_scheduling(orcamento, agendamento)
        wz_url = f"https://wa.me/{wz_numero}?text={wz_msg}"

        return jsonify(
            {
                "status": "ok",
                "agendamento": agendamento.to_dict(),
                "redirect": url_for("agendamento_confirmado", hash_id=hash_id, _external=True),
                "whatsapp_url": wz_url,
            }
        )
    except Exception as e:
        tb = traceback.format_exc()
        print(f"AGENDAR ERROR: {tb}", flush=True)
        app.logger.error(f"AGENDAR ERROR: {tb}")
        db.session.rollback()
        return jsonify({"error": f"Erro ao agendar: {str(e)}"}), 500


@app.route("/agendamento-confirmado")
def agendamento_confirmado():
    hash_id = request.args.get("hash_id", "").strip().upper()
    orcamento = Orcamento.query.filter_by(hash_id=hash_id).first_or_404()
    return render_template(
        "confirmado.html",
        orcamento=orcamento,
        agendamento=orcamento.agendamento,
    )


# ---------------------------------------------------------------------------
# API: SLOTS DISPONIVEIS (para refresh do calendario)
# ---------------------------------------------------------------------------

@app.route("/api/slots-disponiveis")
def api_slots_disponiveis():
    slots = (
        SlotHorario.query
        .filter(
            SlotHorario.disponivel == True,
            SlotHorario.data >= _utcnow().date(),
        )
        .order_by(SlotHorario.data, SlotHorario.hora_inicio)
        .limit(120)
        .all()
    )
    return jsonify(
        [
            {
                "id": s.id,
                "data": s.data.isoformat(),
                "hora_inicio": s.hora_inicio.strftime("%H:%M"),
                "hora_fim": s.hora_fim.strftime("%H:%M"),
            }
            for s in slots
        ]
    )


# ---------------------------------------------------------------------------
# API: EXCLUIR ORCAMENTO
# ---------------------------------------------------------------------------

@app.route("/api/orcamentos/<hash_id>", methods=["DELETE"])
def excluir_orcamento(hash_id):
    orcamento = Orcamento.query.filter_by(hash_id=hash_id.upper()).first()
    if not orcamento:
        return jsonify({"error": "Orcamento nao encontrado."}), 404
    db.session.delete(orcamento)
    db.session.commit()
    return jsonify({"status": "deleted", "hash_id": hash_id.upper()})


# ---------------------------------------------------------------------------
# API: CRIAR REVISAO (duplica um orcamento existente)
# ---------------------------------------------------------------------------

@app.route("/api/orcamentos/<hash_id>/revisao", methods=["POST"])
def criar_revisao(hash_id):
    original = Orcamento.query.filter_by(hash_id=hash_id.upper()).first()
    if not original:
        return jsonify({"error": "Orcamento nao encontrado."}), 404

    validade_dias = Config.PROPOSAL_VALIDITY_DAYS
    revisao = Orcamento(
        cliente_id=original.cliente_id,
        data_emissao=_utcnow(),
        data_validade=_utcnow() + timedelta(days=validade_dias),
        observacoes=original.observacoes,
        valor_total=original.valor_total,
    )
    db.session.add(revisao)
    db.session.flush()

    for item_orig in original.itens:
        novo_item = ItemOrcamento(
            orcamento_id=revisao.id,
            item=item_orig.item,
            descricao=item_orig.descricao,
            quantidade=item_orig.quantidade,
            valor_material=item_orig.valor_material,
            valor_mao_obra=item_orig.valor_mao_obra,
            valor_unitario=item_orig.valor_unitario,
            valor_total=item_orig.valor_total,
            valor_total_material=item_orig.valor_total_material,
            valor_total_mao_obra=item_orig.valor_total_mao_obra,
        )
        db.session.add(novo_item)

    db.session.commit()
    generate_orcamento_pdf(revisao, base_url=_get_base_url())

    return jsonify(
        {
            "id": revisao.id,
            "hash_id": revisao.hash_id,
            "pdf_url": url_for("download_pdf", hash_id=revisao.hash_id, _external=True),
            "status": revisao.status,
        }
    ), 201


# ---------------------------------------------------------------------------
# API: ATUALIZAR STATUS DO ORCAMENTO
# ---------------------------------------------------------------------------

@app.route("/api/orcamentos/<hash_id>/status", methods=["PATCH"])
def atualizar_status(hash_id):
    data = request.get_json(force=True)
    novo_status = data.get("status", "").upper().strip()
    validos = ["PENDENTE", "APROVADO_PELO_CLIENTE", "AGENDADO", "CONCLUIDO", "CANCELADO"]
    if novo_status not in validos:
        return jsonify({"error": f"Status invalido. Validos: {', '.join(validos)}"}), 400

    orcamento = Orcamento.query.filter_by(hash_id=hash_id.upper()).first()
    if not orcamento:
        return jsonify({"error": "Orcamento nao encontrado."}), 404

    orcamento.status = novo_status
    orcamento.atualizado_em = _utcnow()
    db.session.commit()
    return jsonify({"status": "updated", "novo_status": novo_status})


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "DK Electric Help"})


if __name__ == "__main__":
    os.makedirs(Config.PDF_OUTPUT_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
