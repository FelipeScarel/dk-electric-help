import os
import traceback
from datetime import datetime, timedelta, timezone
from io import BytesIO

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from sqlalchemy import func

from config import Config
from database import (
    Agendamento,
    BloqueioAgenda,
    Cliente,
    ConfiguracaoHorario,
    ItemOrcamento,
    NotificationLog,
    Orcamento,
    SlotHorario,
    db,
    init_db,
)
from pdf_generator import generate_orcamento_pdf
from whatsapp_service import notify_approval, notify_scheduling


def _utcnow():
    """Retorna datetime UTC naive (sem tzinfo), compativel com o banco SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Vercel serverless: usa /tmp para PDFs (unico diretorio com permissao de escrita)
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        Config.PDF_OUTPUT_DIR = "/tmp"

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


def login_required(f):
    """Decorator que protege rotas administrativas — exige senha na sessao."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)

    return decorated


app = create_app()


# ---------------------------------------------------------------------------
# AUTENTICACAO
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        if email == Config.ADMIN_EMAIL.lower() and senha == Config.ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            session.permanent = True
            proxima = request.args.get("next") or url_for("listar_orcamentos")
            return redirect(proxima)
        error = "Email ou senha incorretos."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# ROTAS DE PAGINAS
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/orcamentos")
@login_required
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
# API: BUSCAR ORCAMENTOS (server-side search por protocolo, cliente, etc.)
# ---------------------------------------------------------------------------

@app.route("/api/orcamentos/buscar")
@login_required
def buscar_orcamentos():
    """Busca server-side de orcamentos por termo, status e periodo."""
    termo = request.args.get("q", "").strip()
    status_filtro = request.args.get("status", "").strip().upper()
    dias = request.args.get("dias", "").strip()

    query = Orcamento.query.join(Cliente)

    # Filtro por termo (nome, empresa, cidade, telefone, protocolo)
    if termo:
        pattern = f"%{termo}%"
        query = query.filter(
            db.or_(
                Cliente.nome.ilike(pattern),
                Cliente.empresa.ilike(pattern),
                Cliente.cidade.ilike(pattern),
                Cliente.telefone.ilike(pattern),
                Orcamento.hash_id.ilike(pattern),
            )
        )

    # Filtro por status
    if status_filtro:
        query = query.filter(Orcamento.status == status_filtro)

    # Filtro por periodo (dias)
    if dias:
        try:
            dias_int = int(dias)
            if dias_int > 0:
                limite = _utcnow() - timedelta(days=dias_int)
                query = query.filter(Orcamento.criado_em >= limite)
        except ValueError:
            pass

    resultados = (
        query
        .order_by(Orcamento.criado_em.desc())
        .limit(200)
        .all()
    )

    return jsonify({
        "resultados": [
            {
                "hash_id": o.hash_id,
                "nome": o.cliente.nome,
                "empresa": o.cliente.empresa or "",
                "telefone": o.cliente.telefone,
                "endereco": o.cliente.endereco,
                "numero": o.cliente.numero or "",
                "complemento": o.cliente.complemento or "",
                "bairro": o.cliente.bairro or "",
                "cidade": o.cliente.cidade,
                "estado": o.cliente.estado or "",
                "status": o.status,
                "criado_em": o.criado_em.isoformat(),
                "data_validade": o.data_validade.strftime("%d/%m/%Y"),
                "valor_total": f"{o.valor_total:.2f}",
                "itens_count": len(o.itens),
                "agendamento": {
                    "data": o.agendamento.data_agendada.strftime("%d/%m/%Y"),
                    "periodo": o.agendamento.periodo,
                } if o.agendamento else None,
            }
            for o in resultados
        ],
        "total": len(resultados),
    })


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
    pdf_bytes = generate_orcamento_pdf(orcamento, base_url=_get_base_url())
    return send_file(
        BytesIO(pdf_bytes),
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

    # Ja foi agendado pelo admin — mostra confirmacao
    if orcamento.status == "AGENDADO" and orcamento.agendamento:
        return render_template(
            "confirmado.html",
            orcamento=orcamento,
            agendamento=orcamento.agendamento,
        )

    # Cliente aprovou agora OU ja estava aprovado e clicou de novo
    if orcamento.status == "PENDENTE":
        orcamento.status = "APROVADO_PELO_CLIENTE"
        orcamento.atualizado_em = _utcnow()
        db.session.commit()

    # Redireciona direto para o WhatsApp com os dados do orcamento
    numero = Config.WHATSAPP_NOTIFY.strip()
    msg = notify_approval(orcamento)
    whatsapp_url = f"https://api.whatsapp.com/send?phone={numero}&text={msg}"

    return redirect(whatsapp_url)


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

        # Verifica se o slot esta em um periodo bloqueado pelo admin
        bloqueado = BloqueioAgenda.query.filter(
            BloqueioAgenda.data == slot.data,
            db.or_(
                BloqueioAgenda.horario == None,
                BloqueioAgenda.horario == slot.hora_inicio,
            ),
            BloqueioAgenda.status_bloqueio == "BLOQUEADO",
        ).first()
        if bloqueado:
            return jsonify({"error": "Este horario nao esta mais disponivel."}), 409

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
    bloqueio_existe = (
        db.session.query(BloqueioAgenda.id)
        .filter(
            BloqueioAgenda.data == SlotHorario.data,
            db.or_(
                BloqueioAgenda.horario == None,
                BloqueioAgenda.horario == SlotHorario.hora_inicio,
            ),
            BloqueioAgenda.status_bloqueio == "BLOQUEADO",
        )
        .exists()
    )

    slots = (
        SlotHorario.query
        .filter(
            SlotHorario.disponivel == True,
            SlotHorario.data >= _utcnow().date(),
            ~bloqueio_existe,
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
@login_required
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
@login_required
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
@login_required
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
# ADMIN: PAINEL DE CONTROLE DA AGENDA
# ---------------------------------------------------------------------------

@app.route("/admin/agenda")
@login_required
def admin_agenda():
    """Painel de controle da agenda para o administrador."""
    hoje = _utcnow().date()
    data_inicio = hoje
    data_fim = hoje + timedelta(days=60)

    # Estatisticas rapidas
    total_slots = SlotHorario.query.filter(
        SlotHorario.data >= hoje,
        SlotHorario.data <= data_fim,
    ).count()

    bloqueados = (
        db.session.query(BloqueioAgenda)
        .filter(
            BloqueioAgenda.data >= hoje,
            BloqueioAgenda.data <= data_fim,
            BloqueioAgenda.status_bloqueio == "BLOQUEADO",
        )
        .count()
    )

    agendados = Agendamento.query.filter(
        Agendamento.status == "CONFIRMADO",
        Agendamento.data_agendada >= datetime.combine(hoje, datetime.min.time()),
    ).count()

    disponiveis = SlotHorario.query.filter(
        SlotHorario.disponivel == True,
        SlotHorario.data >= hoje,
    ).count()

    # Lista de orcamentos pendentes/aprovados para agendamento manual
    orcamentos_agendaveis = (
        Orcamento.query
        .filter(Orcamento.status.in_(["PENDENTE", "APROVADO_PELO_CLIENTE"]))
        .order_by(Orcamento.criado_em.desc())
        .limit(50)
        .all()
    )

    stats = {
        "total_slots": total_slots,
        "bloqueados": bloqueados,
        "agendados": agendados,
        "disponiveis": disponiveis,
    }

    return render_template(
        "admin_agenda.html",
        stats=stats,
        data_inicio=data_inicio.strftime("%Y-%m-%d"),
        data_fim=data_fim.strftime("%Y-%m-%d"),
        orcamentos_agendaveis=orcamentos_agendaveis,
    )


@app.route("/api/admin/agenda")
@login_required
def api_admin_agenda():
    """Retorna o grid completo da agenda com status de cada slot."""
    hoje = _utcnow().date()
    try:
        di_str = request.args.get("data_inicio", hoje.isoformat())
        df_str = request.args.get("data_fim", (hoje + timedelta(days=60)).isoformat())
        data_inicio = datetime.strptime(di_str, "%Y-%m-%d").date()
        data_fim = datetime.strptime(df_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({"error": "Formato de data invalido. Use YYYY-MM-DD."}), 400

    slots = (
        SlotHorario.query
        .filter(SlotHorario.data >= data_inicio, SlotHorario.data <= data_fim)
        .order_by(SlotHorario.data, SlotHorario.hora_inicio)
        .all()
    )

    # Carrega bloqueios e agendamentos para o periodo
    bloqueios = (
        BloqueioAgenda.query
        .filter(
            BloqueioAgenda.data >= data_inicio,
            BloqueioAgenda.data <= data_fim,
            BloqueioAgenda.status_bloqueio == "BLOQUEADO",
        )
        .all()
    )
    bloqueios_por_data = {}
    for b in bloqueios:
        key = b.data.isoformat()
        if key not in bloqueios_por_data:
            bloqueios_por_data[key] = []
        bloqueios_por_data[key].append(b)

    agendamentos = (
        Agendamento.query
        .filter(
            Agendamento.status == "CONFIRMADO",
            Agendamento.data_agendada >= datetime.combine(data_inicio, datetime.min.time()),
            Agendamento.data_agendada <= datetime.combine(data_fim, datetime.max.time()),
        )
        .all()
    )
    agendamentos_por_data = {}
    for a in agendamentos:
        key = a.data_agendada.date().isoformat()
        if key not in agendamentos_por_data:
            agendamentos_por_data[key] = []
        agendamentos_por_data[key].append(a)

    dias = {}
    for s in slots:
        dia_key = s.data.isoformat()
        if dia_key not in dias:
            dias[dia_key] = {
                "data": dia_key,
                "dia_semana": _dia_semana_pt(s.data.weekday()),
                "slots": [],
            }

        status = "disponivel"
        bloqueio_id = None
        motivo_bloqueio = None
        agendamento_info = None

        # Verifica bloqueio
        blks = bloqueios_por_data.get(dia_key, [])
        for b in blks:
            if b.horario is None or b.horario == s.hora_inicio:
                status = "bloqueado"
                bloqueio_id = b.id
                motivo_bloqueio = b.motivo_bloqueio
                break

        # Verifica agendamento (sobrescreve bloqueio se ja tem agendamento ativo)
        if not s.disponivel and s.agendamento_id:
            ags = agendamentos_por_data.get(dia_key, [])
            for a in ags:
                slot_start = s.hora_inicio.strftime("%H:%M")
                ag_periodo_start = a.periodo.split(" - ")[0] if " - " in a.periodo else a.periodo[:5]
                if a.id == s.agendamento_id:
                    status = "agendado"
                    agendamento_info = {
                        "id": a.id,
                        "cliente": a.orcamento.cliente.nome if a.orcamento and a.orcamento.cliente else "",
                        "hash_id": a.orcamento.hash_id if a.orcamento else "",
                        "periodo": a.periodo,
                    }
                    break

        dias[dia_key]["slots"].append({
            "id": s.id,
            "hora_inicio": s.hora_inicio.strftime("%H:%M"),
            "hora_fim": s.hora_fim.strftime("%H:%M"),
            "disponivel": s.disponivel,
            "status": status,
            "bloqueio_id": bloqueio_id,
            "motivo_bloqueio": motivo_bloqueio,
            "agendamento": agendamento_info,
        })

    dias_list = sorted(dias.values(), key=lambda d: d["data"])

    total_s = sum(len(d["slots"]) for d in dias_list)
    disponiveis_count = sum(1 for d in dias_list for s in d["slots"] if s["status"] == "disponivel")
    bloqueados_count = sum(1 for d in dias_list for s in d["slots"] if s["status"] == "bloqueado")
    agendados_count = sum(1 for d in dias_list for s in d["slots"] if s["status"] == "agendado")

    return jsonify({
        "dias": dias_list,
        "stats": {
            "total_slots": total_s,
            "disponiveis": disponiveis_count,
            "bloqueados": bloqueados_count,
            "agendados": agendados_count,
        },
    })


def _dia_semana_pt(weekday):
    """Converte 0=Monday para nome em portugues."""
    nomes = ["Segunda-feira", "Terca-feira", "Quarta-feira",
             "Quinta-feira", "Sexta-feira", "Sabado", "Domingo"]
    return nomes[weekday] if 0 <= weekday <= 6 else ""


@app.route("/api/admin/bloquear", methods=["POST"])
@login_required
def admin_bloquear():
    """Bloqueia um intervalo de datas ou periodo especifico."""
    try:
        data = request.get_json(force=True)
        data_inicio = datetime.strptime(data["data_inicio"], "%Y-%m-%d").date()
        data_fim = datetime.strptime(data["data_fim"], "%Y-%m-%d").date()
        horario_str = data.get("horario")  # None = dia inteiro, "08:00" = periodo especifico
        motivo = data.get("motivo_bloqueio", "").strip()
        admin_resp = data.get("admin_responsavel", "").strip()

        if data_inicio > data_fim:
            return jsonify({"error": "Data inicio deve ser anterior a data fim."}), 400
    except (KeyError, ValueError):
        return jsonify({"error": "Dados invalidos. Envie data_inicio e data_fim no formato YYYY-MM-DD."}), 400

    horario_time = None
    if horario_str:
        try:
            horario_time = datetime.strptime(horario_str, "%H:%M").time()
        except ValueError:
            return jsonify({"error": "Formato de horario invalido. Use HH:MM."}), 400

    delta = (data_fim - data_inicio).days + 1
    bloqueios_criados = 0
    slots_afetados = 0

    for offset in range(delta):
        dia = data_inicio + timedelta(days=offset)
        if dia.weekday() >= 5:
            continue  # Pula fins de semana

        # Se horario for None, bloqueia dia inteiro com um unico registro
        if horario_time is None:
            existente = BloqueioAgenda.query.filter_by(
                data=dia, horario=None, status_bloqueio="BLOQUEADO"
            ).first()
            if not existente:
                b = BloqueioAgenda(
                    data=dia,
                    horario=None,
                    motivo_bloqueio=motivo,
                    admin_responsavel=admin_resp,
                )
                db.session.add(b)
                bloqueios_criados += 1

            # Marca todos os slots do dia como indisponiveis
            slots_dia = SlotHorario.query.filter_by(data=dia).all()
            for s in slots_dia:
                if s.disponivel:
                    s.disponivel = False
                    slots_afetados += 1
        else:
            # Bloqueia apenas periodo especifico
            existente = BloqueioAgenda.query.filter_by(
                data=dia, horario=horario_time, status_bloqueio="BLOQUEADO"
            ).first()
            if not existente:
                b = BloqueioAgenda(
                    data=dia,
                    horario=horario_time,
                    motivo_bloqueio=motivo,
                    admin_responsavel=admin_resp,
                )
                db.session.add(b)
                bloqueios_criados += 1

            slot = SlotHorario.query.filter_by(data=dia, hora_inicio=horario_time).first()
            if slot and slot.disponivel:
                slot.disponivel = False
                slots_afetados += 1

    db.session.commit()

    return jsonify({
        "status": "ok",
        "bloqueios_criados": bloqueios_criados,
        "slots_afetados": slots_afetados,
        "mensagem": f"{bloqueios_criados} dia(s)/periodo(s) bloqueado(s). {slots_afetados} slot(s) indisponibilizado(s).",
    })


@app.route("/api/admin/bloquear/<int:bloqueio_id>", methods=["DELETE"])
@login_required
def admin_desbloquear(bloqueio_id):
    """Remove um bloqueio e libera os slots correspondentes."""
    bloqueio = BloqueioAgenda.query.get(bloqueio_id)
    if not bloqueio:
        return jsonify({"error": "Bloqueio nao encontrado."}), 404

    data_bloqueio = bloqueio.data
    horario_bloqueio = bloqueio.horario

    bloqueio.status_bloqueio = "LIBERADO"
    db.session.flush()

    # Restaura slots que nao possuem agendamento ativo
    slots_liberados = 0
    if horario_bloqueio is None:
        # Dia inteiro
        slots = SlotHorario.query.filter_by(data=data_bloqueio).all()
        for s in slots:
            if not s.agendamento_id:
                s.disponivel = True
                slots_liberados += 1
    else:
        slot = SlotHorario.query.filter_by(data=data_bloqueio, hora_inicio=horario_bloqueio).first()
        if slot and not slot.agendamento_id:
            slot.disponivel = True
            slots_liberados = 1

    db.session.commit()

    return jsonify({
        "status": "ok",
        "slots_liberados": slots_liberados,
        "mensagem": f"Bloqueio removido. {slots_liberados} slot(s) liberado(s).",
    })


@app.route("/api/admin/agendar-manual", methods=["POST"])
@login_required
def admin_agendar_manual():
    """Forca o agendamento manual de um cliente por fora do fluxo do PDF."""
    try:
        data = request.get_json(force=True)
        hash_id = data.get("hash_id", "").strip().upper()
        data_str = data.get("data")
        periodo = data.get("periodo", "").strip()

        if not hash_id or not data_str or not periodo:
            return jsonify({"error": "hash_id, data e periodo sao obrigatorios."}), 400

        orcamento = Orcamento.query.filter_by(hash_id=hash_id).first()
        if not orcamento:
            return jsonify({"error": "Orcamento nao encontrado."}), 404

        data_ag = datetime.strptime(data_str, "%Y-%m-%d").date()
        hora_inicio = datetime.strptime(periodo.split(" - ")[0], "%H:%M").time()
        hora_fim = datetime.strptime(periodo.split(" - ")[1], "%H:%M").time()
    except (ValueError, KeyError, IndexError):
        return jsonify({"error": "Dados invalidos. Use data=YYYY-MM-DD e periodo=HH:MM - HH:MM"}), 400

    # Encontra ou cria o slot
    slot = SlotHorario.query.filter_by(data=data_ag, hora_inicio=hora_inicio).first()
    if not slot:
        slot = SlotHorario(
            data=data_ag,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            disponivel=False,
        )
        db.session.add(slot)
        db.session.flush()
    elif not slot.disponivel:
        return jsonify({"error": "Horario ja esta ocupado ou bloqueado."}), 409

    slot.disponivel = False

    agendamento = Agendamento(
        orcamento_id=orcamento.id,
        data_agendada=datetime.combine(data_ag, hora_inicio),
        periodo=periodo,
        observacoes_cliente=data.get("observacoes", "Agendamento manual pelo administrador"),
        criado_por_admin=True,
        status="MANUAL",
    )
    db.session.add(agendamento)
    db.session.flush()
    slot.agendamento_id = agendamento.id

    orcamento.status = "AGENDADO"
    orcamento.atualizado_em = _utcnow()
    db.session.commit()

    return jsonify({
        "status": "ok",
        "agendamento": agendamento.to_dict(),
        "mensagem": f"Agendamento manual criado para {orcamento.cliente.nome} em {data_ag.strftime('%d/%m/%Y')} {periodo}.",
    }), 201


@app.route("/api/admin/agendamento/<int:agendamento_id>/reagendar", methods=["POST"])
@login_required
def admin_reagendar(agendamento_id):
    """Reagenda um servico ja marcado, mantendo o historico."""
    ag_antigo = Agendamento.query.get(agendamento_id)
    if not ag_antigo:
        return jsonify({"error": "Agendamento nao encontrado."}), 404

    try:
        data_r = request.get_json(force=True)
        nova_data_str = data_r["nova_data"]
        novo_periodo = data_r["novo_periodo"].strip()

        nova_data = datetime.strptime(nova_data_str, "%Y-%m-%d").date()
        hora_inicio = datetime.strptime(novo_periodo.split(" - ")[0], "%H:%M").time()
        hora_fim = datetime.strptime(novo_periodo.split(" - ")[1], "%H:%M").time()
    except (KeyError, ValueError, IndexError):
        return jsonify({"error": "Dados invalidos. Use nova_data=YYYY-MM-DD e novo_periodo=HH:MM - HH:MM"}), 400

    # Libera slot antigo
    slot_antigo = SlotHorario.query.filter_by(
        data=ag_antigo.data_agendada.date(),
        hora_inicio=ag_antigo.data_agendada.time(),
    ).first()
    if slot_antigo:
        slot_antigo.disponivel = True
        slot_antigo.agendamento_id = None

    # Encontra/cria novo slot
    slot_novo = SlotHorario.query.filter_by(data=nova_data, hora_inicio=hora_inicio).first()
    if not slot_novo:
        slot_novo = SlotHorario(
            data=nova_data,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            disponivel=False,
        )
        db.session.add(slot_novo)
        db.session.flush()
    elif not slot_novo.disponivel:
        return jsonify({"error": "Novo horario ja esta ocupado."}), 409

    slot_novo.disponivel = False

    # Marca antigo como reagendado
    ag_antigo.status = "REAGENDADO"

    # Cria novo agendamento
    novo_ag = Agendamento(
        orcamento_id=ag_antigo.orcamento_id,
        data_agendada=datetime.combine(nova_data, hora_inicio),
        periodo=novo_periodo,
        observacoes_cliente=f"Reagendado de {ag_antigo.data_agendada.strftime('%d/%m/%Y')} {ag_antigo.periodo}",
        criado_por_admin=True,
        status="MANUAL",
        reagendado_de=ag_antigo.id,
    )
    db.session.add(novo_ag)
    db.session.flush()
    slot_novo.agendamento_id = novo_ag.id

    db.session.commit()

    return jsonify({
        "status": "ok",
        "agendamento_antigo": ag_antigo.to_dict(),
        "novo_agendamento": novo_ag.to_dict(),
        "mensagem": f"Reagendado de {ag_antigo.data_agendada.strftime('%d/%m/%Y')} para {nova_data.strftime('%d/%m/%Y')} {novo_periodo}.",
    })


@app.route("/api/admin/agendamento/<int:agendamento_id>", methods=["DELETE"])
@login_required
def admin_cancelar_agendamento(agendamento_id):
    """Cancela um agendamento e libera o slot."""
    ag = Agendamento.query.get(agendamento_id)
    if not ag:
        return jsonify({"error": "Agendamento nao encontrado."}), 404

    data_r = request.get_json(silent=True) or {}
    motivo = data_r.get("motivo_cancelamento", "").strip()

    ag.status = "CANCELADO"
    ag.motivo_cancelamento = motivo or "Cancelado pelo administrador"

    # Libera o slot
    slot = SlotHorario.query.filter_by(agendamento_id=ag.id).first()
    if slot:
        slot.disponivel = True
        slot.agendamento_id = None

    # Opcionalmente, volta orcamento para status anterior
    if ag.orcamento:
        ag.orcamento.status = "APROVADO_PELO_CLIENTE"
        ag.orcamento.atualizado_em = _utcnow()

    db.session.commit()

    return jsonify({
        "status": "ok",
        "mensagem": f"Agendamento #{ag.id} cancelado. Slot liberado.",
    })


@app.route("/api/admin/limpar-dia/<data_str>", methods=["POST"])
@login_required
def admin_limpar_dia(data_str):
    """Limpa toda a grade de horarios de um dia especifico."""
    try:
        data_alvo = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Formato de data invalido. Use YYYY-MM-DD."}), 400

    # Cancela todos os agendamentos do dia
    ags = Agendamento.query.filter(
        Agendamento.data_agendada >= datetime.combine(data_alvo, datetime.min.time()),
        Agendamento.data_agendada <= datetime.combine(data_alvo, datetime.max.time()),
        Agendamento.status == "CONFIRMADO",
    ).all()

    agendamentos_cancelados = 0
    for a in ags:
        a.status = "CANCELADO"
        a.motivo_cancelamento = "Dia limpo pelo administrador"
        agendamentos_cancelados += 1
        if a.orcamento:
            a.orcamento.status = "APROVADO_PELO_CLIENTE"
            a.orcamento.atualizado_em = _utcnow()

    # Remove agendamento_id de todos os slots do dia
    slots = SlotHorario.query.filter_by(data=data_alvo).all()
    for s in slots:
        s.agendamento_id = None

    db.session.flush()

    # Cria bloqueio para o dia inteiro
    existente = BloqueioAgenda.query.filter_by(
        data=data_alvo, horario=None, status_bloqueio="BLOQUEADO"
    ).first()
    if not existente:
        b = BloqueioAgenda(
            data=data_alvo,
            horario=None,
            motivo_bloqueio="Dia limpo pelo administrador",
            admin_responsavel="Admin",
        )
        db.session.add(b)

    # Marca todos os slots como indisponiveis
    slots_bloqueados = 0
    for s in slots:
        if s.disponivel:
            s.disponivel = False
            slots_bloqueados += 1

    db.session.commit()

    return jsonify({
        "status": "ok",
        "agendamentos_cancelados": agendamentos_cancelados,
        "slots_bloqueados": slots_bloqueados,
        "mensagem": f"Dia {data_alvo.strftime('%d/%m/%Y')} limpo. {agendamentos_cancelados} agendamento(s) cancelado(s), {slots_bloqueados} slot(s) bloqueado(s).",
    })


@app.route("/api/admin/liberar-todos", methods=["POST"])
@login_required
def admin_liberar_todos():
    """Libera todos os bloqueios ativos e restaura slots nao agendados."""
    hoje = _utcnow().date()

    bloqueios = BloqueioAgenda.query.filter(
        BloqueioAgenda.data >= hoje,
        BloqueioAgenda.status_bloqueio == "BLOQUEADO",
    ).all()

    bloqueios_liberados = 0
    for b in bloqueios:
        b.status_bloqueio = "LIBERADO"
        bloqueios_liberados += 1

    db.session.flush()

    # Restaura slots que nao tem agendamento
    slots = SlotHorario.query.filter(
        SlotHorario.data >= hoje,
        SlotHorario.agendamento_id == None,
    ).all()

    slots_liberados = 0
    for s in slots:
        if not s.disponivel:
            s.disponivel = True
            slots_liberados += 1

    db.session.commit()

    return jsonify({
        "status": "ok",
        "bloqueios_liberados": bloqueios_liberados,
        "slots_liberados": slots_liberados,
        "mensagem": f"Todos os dias liberados. {bloqueios_liberados} bloqueio(s) removido(s), {slots_liberados} slot(s) restaurado(s).",
    })


# ---------------------------------------------------------------------------
# ADMIN: CONFIGURACAO DE HORARIOS SEMANAIS
# ---------------------------------------------------------------------------

@app.route("/api/admin/configuracao")
@login_required
def api_configuracao_horarios():
    """Retorna a configuracao semanal de horarios."""
    configs = (
        ConfiguracaoHorario.query
        .order_by(ConfiguracaoHorario.dia_semana, ConfiguracaoHorario.hora_inicio)
        .all()
    )
    return jsonify([c.to_dict() for c in configs])


@app.route("/api/admin/configuracao", methods=["POST"])
@login_required
def api_criar_configuracao():
    """Adiciona um novo periodo a um dia da semana."""
    try:
        data = request.get_json(force=True)
        dia_semana = int(data["dia_semana"])  # 0=Seg ... 4=Sex, 5=Sab, 6=Dom
        hora_inicio = datetime.strptime(data["hora_inicio"], "%H:%M").time()
        hora_fim = datetime.strptime(data["hora_fim"], "%H:%M").time()

        if dia_semana < 0 or dia_semana > 6:
            return jsonify({"error": "dia_semana deve ser 0 (Seg) a 6 (Dom)."}), 400

        if hora_inicio >= hora_fim:
            return jsonify({"error": "Hora inicio deve ser anterior a hora fim."}), 400

        # Verifica conflito
        conflito = ConfiguracaoHorario.query.filter_by(
            dia_semana=dia_semana, hora_inicio=hora_inicio
        ).first()
        if conflito:
            return jsonify({"error": "Ja existe um periodo com este horario de inicio neste dia."}), 409

        cfg = ConfiguracaoHorario(
            dia_semana=dia_semana,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            ativo=data.get("ativo", True),
        )
        db.session.add(cfg)
        db.session.commit()

        return jsonify({"status": "ok", "configuracao": cfg.to_dict()}), 201
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Dados invalidos: {str(e)}"}), 400


@app.route("/api/admin/configuracao/<int:cfg_id>", methods=["PUT"])
@login_required
def api_atualizar_configuracao(cfg_id):
    """Atualiza um periodo (horarios, ativo/inativo)."""
    cfg = ConfiguracaoHorario.query.get(cfg_id)
    if not cfg:
        return jsonify({"error": "Configuracao nao encontrada."}), 404

    try:
        data = request.get_json(force=True)
        if "hora_inicio" in data:
            cfg.hora_inicio = datetime.strptime(data["hora_inicio"], "%H:%M").time()
        if "hora_fim" in data:
            cfg.hora_fim = datetime.strptime(data["hora_fim"], "%H:%M").time()
        if "ativo" in data:
            cfg.ativo = bool(data["ativo"])
        if "dia_semana" in data:
            ns = int(data["dia_semana"])
            if 0 <= ns <= 6:
                cfg.dia_semana = ns

        if cfg.hora_inicio >= cfg.hora_fim:
            return jsonify({"error": "Hora inicio deve ser anterior a hora fim."}), 400

        db.session.commit()
        return jsonify({"status": "ok", "configuracao": cfg.to_dict()})
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Dados invalidos: {str(e)}"}), 400


@app.route("/api/admin/configuracao/<int:cfg_id>", methods=["DELETE"])
@login_required
def api_excluir_configuracao(cfg_id):
    """Remove um periodo da configuracao semanal."""
    cfg = ConfiguracaoHorario.query.get(cfg_id)
    if not cfg:
        return jsonify({"error": "Configuracao nao encontrada."}), 404
    db.session.delete(cfg)
    db.session.commit()
    return jsonify({"status": "deleted", "id": cfg_id})


@app.route("/api/admin/regenerar-slots", methods=["POST"])
@login_required
def api_regenerar_slots():
    """Regenera todos os slots futuros com base na configuracao atual."""
    try:
        from database import _seed_slots
        _seed_slots(app)
        total = SlotHorario.query.filter(SlotHorario.data >= _utcnow().date()).count()
        return jsonify({
            "status": "ok",
            "slots_gerados": total,
            "mensagem": f"Slots regenerados com sucesso. {total} slots disponiveis.",
        })
    except Exception as e:
        return jsonify({"error": f"Erro ao regenerar slots: {str(e)}"}), 500


# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "DK Electric Help"})


if __name__ == "__main__":
    os.makedirs(Config.PDF_OUTPUT_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
