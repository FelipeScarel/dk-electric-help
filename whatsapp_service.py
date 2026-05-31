"""
DK Electric Help - WhatsApp Notification
Envia alerta de novo agendamento via Meta WhatsApp Cloud API.
Simples, direto, sem dependencias externas.
"""

import json
import os
import urllib.error
import urllib.request

from config import Config
from database import NotificationLog, db


def _build_message(orcamento, agendamento) -> str:
    cliente = orcamento.cliente
    valor = f"R$ {orcamento.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    servicos = "\n".join(
        f"  - {i.descricao[:50]}: R$ {i.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        for i in orcamento.itens
    )
    obs = orcamento.observacoes.strip() or "Nenhuma"
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
        f"*Orcamento:* {orcamento.hash_id}"
    )


def notify_scheduling(orcamento, agendamento) -> dict:
    """Envia notificacao WhatsApp usando Meta Cloud API."""
    from flask import current_app
    app = current_app._get_current_object()

    token = Config.META_WHATSAPP_TOKEN.strip()
    phone_id = Config.META_WHATSAPP_PHONE_ID.strip()
    phone = Config.WHATSAPP_NOTIFY.strip()

    if not token or not phone_id:
        print("[WPP] Meta API nao configurada.", flush=True)
        return {"status": "skipped"}

    mensagem = _build_message(orcamento, agendamento)
    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    body = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"preview_url": False, "body": mensagem},
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())
            msg_id = result.get("messages", [{}])[0].get("id", "ok")
            print(f"[WPP] ENVIADO! ID: {msg_id}", flush=True)

            # Log no banco
            try:
                with app.app_context():
                    log = NotificationLog(
                        agendamento_id=agendamento.id,
                        phone_to=phone,
                        status="sent",
                        message_body=mensagem[:500],
                        response=f"id={msg_id}",
                        attempts=1,
                    )
                    db.session.add(log)
                    db.session.commit()
            except Exception as e:
                print(f"[WPP] Erro log: {e}", flush=True)

            return {"status": "sent", "msg_id": msg_id}

    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else str(e)
        print(f"[WPP] ERRO Meta ({e.code}): {err[:300]}", flush=True)
        try:
            with app.app_context():
                log = NotificationLog(
                    agendamento_id=agendamento.id,
                    phone_to=phone,
                    status="failed",
                    message_body=mensagem[:500],
                    response=str(err)[:500],
                    attempts=1,
                )
                db.session.add(log)
                db.session.commit()
        except Exception:
            pass
        return {"status": "failed", "error": str(err)[:200]}

    except Exception as e:
        print(f"[WPP] ERRO: {e}", flush=True)
        return {"status": "failed", "error": str(e)[:200]}
