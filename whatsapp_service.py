"""
DK Electric Help - WhatsApp Notification Service

Envia automaticamente para os socios quando um cliente agenda.
Usa pywhatkit (WhatsApp Web) localmente - simples, sem API externa.
Suporta Evolution API como opcao para deploy em servidor.

Numeros: 5519996387901 / 5519987203886
"""

import os
import threading
from datetime import datetime

from config import Config
from database import NotificationLog, db


def _build_message(orcamento, agendamento) -> str:
    """Monta a mensagem formatada do agendamento."""
    cliente = orcamento.cliente
    valor = f"R$ {orcamento.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    servicos = "\n".join(
        f"  - {i.descricao[:50]}: R$ {i.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        for i in orcamento.itens
    )

    obs = orcamento.observacoes.strip() if orcamento.observacoes else "Nenhuma"

    return (
        f"*NOVO AGENDAMENTO CONFIRMADO*\n\n"
        f"*Cliente:* {cliente.nome}\n"
        f"*Data:* {agendamento.data_agendada.strftime('%d/%m/%Y')}\n"
        f"*Hora:* {agendamento.periodo}\n\n"
        f"*Endereco:*\n{cliente.endereco}\n"
        f"*Cidade:* {cliente.cidade}\n"
        f"*Telefone:* {cliente.telefone}\n"
        + (f"*Empresa:* {cliente.empresa}\n" if cliente.empresa else "") +
        f"\n*Servicos:*\n{servicos}\n\n"
        f"*Valor:* {valor}\n\n"
        f"*Obs:* {obs}\n\n"
        f"*Orcamento:* {orcamento.hash_id}\n"
        f"_DK Electric Help_"
    )


def _log(app, agendamento_id, phone, status, message, response="", attempts=1):
    """Salva log de notificacao no banco (com contexto Flask)."""
    try:
        with app.app_context():
            log = NotificationLog(
                agendamento_id=agendamento_id,
                phone_to=phone,
                status=status,
                message_body=message[:500] if message else "",
                response=str(response)[:500],
                attempts=attempts,
            )
            db.session.add(log)
            db.session.commit()
    except Exception as e:
        print(f"[WHATSAPP] Erro ao salvar log: {e}", flush=True)


def _send_via_pywhatkit(phone: str, message: str) -> str:
    """Envia mensagem via pywhatkit (WhatsApp Web). Retorna 'ok' ou mensagem de erro."""
    try:
        import pywhatkit as pwk
        # pywhatkit espera numero sem + e com country_code separado
        # Remove +55 se existir e passa como parametro
        if phone.startswith("55"):
            number = phone[2:]  # remove prefixo 55
        elif phone.startswith("+55"):
            number = phone[3:]  # remove prefixo +55
        else:
            number = phone

        pwk.sendwhatmsg_instantly(
            phone_no=f"+55{number}",
            message=message,
            wait_time=12,
            tab_close=True,
            close_time=3,
        )
        return "ok"
    except ImportError:
        return "pywhatkit nao instalado. Execute: pip install pywhatkit"
    except Exception as e:
        return str(e)[:300]


def _send_via_evolution(phone: str, message: str) -> str:
    """Envia via Evolution API (opcional, para deploy em servidor)."""
    import json
    import urllib.request
    import urllib.error

    api_url = (os.environ.get("EVOLUTION_API_URL") or "").strip().rstrip("/")
    api_key = (os.environ.get("EVOLUTION_API_KEY") or "").strip()
    instance = (os.environ.get("EVOLUTION_INSTANCE") or "dk-electric").strip()

    if not api_url or not api_key:
        return "Evolution API nao configurada"

    url = f"{api_url}/message/sendText/{instance}"
    body = json.dumps({"number": phone, "text": message}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "apikey": api_key,
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return "ok" if resp.status in (200, 201) else f"HTTP {resp.status}"
    except Exception as e:
        return str(e)[:300]


def _send_to_phone(app, phone: str, mensagem: str, agendamento_id: int):
    """Envia mensagem para um numero. Tenta pywhatkit primeiro, depois Evolution API."""
    print(f"[WHATSAPP] Enviando para {phone}...", flush=True)

    # Tenta pywhatkit primeiro (local)
    result = _send_via_pywhatkit(phone, mensagem)
    if result != "ok":
        print(f"[WHATSAPP] pywhatkit falhou: {result[:100]}", flush=True)
        # Tenta Evolution API como fallback
        result = _send_via_evolution(phone, mensagem)

    status = "sent" if result == "ok" else "failed"
    print(f"[WHATSAPP] {phone}: {status.upper()}" + (f" ({result[:80]})" if result != "ok" else ""), flush=True)

    _log(app, agendamento_id, phone, status, mensagem, result)
    return result


def notify_scheduling(orcamento, agendamento) -> dict:
    """
    Dispara notificacao WhatsApp para os dois socios.
    Roda em thread separada - nao bloqueia o agendamento.
    """
    from flask import current_app
    app = current_app._get_current_object()

    mensagem = _build_message(orcamento, agendamento)

    phones = [
        Config.WHATSAPP_SOCIO_1.strip(),
        Config.WHATSAPP_SOCIO_2.strip(),
    ]
    phones = [p for p in phones if p]

    if not phones:
        print("[WHATSAPP] Nenhum telefone configurado.", flush=True)
        return {"status": "skipped"}

    # Dispara envios em paralelo via threads
    threads = []
    for phone in phones:
        t = threading.Thread(
            target=_send_to_phone,
            args=(app, phone, mensagem, agendamento.id),
            daemon=True,
        )
        t.start()
        threads.append(t)

    # Nao espera - retorna imediatamente. As threads rodam em background.
    print(f"[WHATSAPP] {len(threads)} notificacoes disparadas em background.", flush=True)
    return {"status": "dispatched", "recipients": len(phones)}
