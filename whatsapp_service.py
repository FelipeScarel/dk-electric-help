"""
DK Electric Help - WhatsApp Notification Service
Utiliza Evolution API com instancia propria conectada via QR Code.

Dependencias:
- Evolution API rodando (Docker ou servidor proprio)
- Instancia conectada via QR Code no WhatsApp

Configuracao (env vars ou config.py):
- EVOLUTION_API_URL: URL base da Evolution API (ex: http://localhost:8080)
- EVOLUTION_API_KEY: API Key da instancia
- EVOLUTION_INSTANCE: Nome da instancia (default: dk-electric)
- WHATSAPP_SOCIO_1 / WHATSAPP_SOCIO_2: Numeros dos socios
"""

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime

from config import Config
from database import NotificationLog, db


def _send_text(phone: str, text: str) -> dict:
    """
    Envia mensagem de texto via Evolution API.
    Retorna dict com status e resposta.
    """
    api_url = (os.environ.get("EVOLUTION_API_URL") or Config.EVOLUTION_API_URL).strip().rstrip("/")
    api_key = (os.environ.get("EVOLUTION_API_KEY") or Config.EVOLUTION_API_KEY).strip()
    instance = (os.environ.get("EVOLUTION_INSTANCE") or Config.EVOLUTION_INSTANCE).strip()

    if not api_url or not api_key:
        return {"success": False, "error": "Evolution API nao configurada.", "http_status": None}

    url = f"{api_url}/message/sendText/{instance}"
    body = json.dumps({"number": phone, "text": text}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "apikey": api_key,
        "User-Agent": "DK-Electric-Help/2.0",
    }

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode()
            return {
                "success": resp.status in (200, 201),
                "http_status": resp.status,
                "response": resp_body[:500],
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        return {"success": False, "http_status": e.code, "response": err_body[:500], "error": str(e)}
    except Exception as e:
        return {"success": False, "http_status": None, "response": str(e), "error": str(e)}


def _build_message(orcamento, agendamento) -> str:
    """Monta a mensagem formatada do agendamento."""
    cliente = orcamento.cliente
    valor = f"R$ {orcamento.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    obs = orcamento.observacoes.strip() if orcamento.observacoes else "Nenhuma"

    # Lista de servicos
    servicos = "\n".join(
        f"  - {i.descricao[:50]}: R$ {i.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        for i in orcamento.itens
    )

    return (
        f"\U0001F4C5 *NOVO AGENDAMENTO CONFIRMADO*\n\n"
        f"\U0001F464 *Cliente:* {cliente.nome}\n"
        f"\U0001F4C6 *Data:* {agendamento.data_agendada.strftime('%d/%m/%Y')}\n"
        f"⏰ *Hora:* {agendamento.periodo}\n\n"
        f"\U0001F4CD *Endereco:*\n{cliente.endereco}\n"
        f"*Cidade:* {cliente.cidade}\n"
        f"*Telefone:* {cliente.telefone}\n"
        f"{'*Empresa:* ' + cliente.empresa if cliente.empresa else ''}\n\n"
        f"\U0001F527 *Servicos:*\n{servicos}\n\n"
        f"\U0001F4B0 *Valor do orcamento:*\n{valor}\n\n"
        f"\U0001F4DD *Observacoes:*\n{obs}\n\n"
        f"*Orcamento:* {orcamento.hash_id}\n"
        f"*DK Electric Help*"
    )


def _log_notification(agendamento_id, phone, status, message, response, attempts):
    """Registra tentativa de notificacao no banco."""
    try:
        log = NotificationLog(
            agendamento_id=agendamento_id,
            phone_to=phone,
            status=status,
            message_body=message[:500] if message else "",
            response=response[:500] if response else "",
            attempts=attempts,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"[WHATSAPP] Erro ao salvar log: {e}", flush=True)
        db.session.rollback()


def notify_scheduling(orcamento, agendamento) -> dict:
    """
    Envia notificacao WhatsApp para os socios sobre novo agendamento.
    Fluxo: montar mensagem -> enviar para socio 1 -> enviar para socio 2 -> registrar logs.
    Suporta retentativa automatica em caso de falha.
    """
    MAX_RETRIES = 2
    RETRY_DELAY = 3  # segundos

    mensagem = _build_message(orcamento, agendamento)

    phones = [
        (os.environ.get("WHATSAPP_SOCIO_1") or Config.WHATSAPP_SOCIO_1).strip(),
        (os.environ.get("WHATSAPP_SOCIO_2") or Config.WHATSAPP_SOCIO_2).strip(),
    ]
    phones = [p for p in phones if p]

    if not phones:
        print("[WHATSAPP] Nenhum telefone configurado.", flush=True)
        return {"status": "skipped", "reason": "no phones"}

    results = {}
    for phone in phones:
        success = False
        last_response = ""
        attempts = 0

        for attempt in range(1, MAX_RETRIES + 1):
            attempts = attempt
            print(f"[WHATSAPP] Enviando para {phone} (tentativa {attempt}/{MAX_RETRIES})...", flush=True)
            result = _send_text(phone, mensagem)

            if result["success"]:
                success = True
                last_response = result.get("response", "OK")
                print(f"[WHATSAPP] OK - {phone}", flush=True)
                break
            else:
                last_response = result.get("response", result.get("error", "unknown"))
                print(f"[WHATSAPP] FALHA {phone}: {last_response[:150]}", flush=True)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        status = "sent" if success else "failed"
        results[phone] = status

        # Registrar no banco
        _log_notification(
            agendamento_id=agendamento.id,
            phone=phone,
            status=status,
            message=mensagem,
            response=last_response,
            attempts=attempts,
        )

    all_sent = all(v == "sent" for v in results.values())
    return {"status": "completed" if all_sent else "partial", "results": results}
