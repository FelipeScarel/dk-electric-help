"""
Servico profissional de notificacao WhatsApp para DK Electric Help.
Dispara mensagens automaticas para os socios quando um cliente agenda.

Usa a Meta WhatsApp Cloud API (gratuita para ate 1000 msgs/mes).
Os destinatarios NAO precisam adicionar contatos nem fazer nada -
recebem as mensagens diretamente no WhatsApp como se fossem normais.

Para ativar: configure as env vars META_WHATSAPP_TOKEN e META_WHATSAPP_PHONE_ID
no dashboard do Render ou no .env local.
"""

import json
import os
import urllib.error
import urllib.request

from config import Config


def _send_whatsapp(phone: str, message: str) -> bool:
    """Envia mensagem via Meta WhatsApp Cloud API (oficial, profissional)."""
    token = (os.environ.get("META_WHATSAPP_TOKEN") or "").strip()
    phone_id = (os.environ.get("META_WHATSAPP_PHONE_ID") or "").strip()

    if not token or not phone_id:
        return False

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    body = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DK-Electric-Help/1.0",
    }

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if resp.status == 200 or resp.status == 201:
                print(f"[WHATSAPP] Enviado para {phone} - msg ID: {result.get('messages', [{}])[0].get('id', 'ok')}")
                return True
            print(f"[WHATSAPP] Erro Meta API ({resp.status}): {result}")
            return False
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"[WHATSAPP] HTTP {e.code} para {phone}: {body[:300]}")
        return False
    except Exception as e:
        print(f"[WHATSAPP] Erro para {phone}: {e}")
        return False


def notify_scheduling(orcamento, agendamento) -> dict:
    """
    Notifica os socios via WhatsApp sobre um novo agendamento.
    Se META_WHATSAPP_TOKEN nao estiver configurado, apenas loga a mensagem.
    """
    cliente = orcamento.cliente

    # Formata itens
    linhas_itens = []
    for i in orcamento.itens:
        valor = f"R$ {i.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        linhas_itens.append(f"  - {i.descricao[:50]}  |  {valor}")
    itens_txt = "\n".join(linhas_itens) if linhas_itens else "Nenhum item"

    valor_total = f"R$ {orcamento.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    mensagem = (
        f"*NOVO AGENDAMENTO - DK ELECTRIC HELP*\n"
        f"{'='*35}\n\n"
        f"*Cliente:* {cliente.nome}\n"
        f"*Empresa:* {cliente.empresa or '---'}\n"
        f"*Telefone:* {cliente.telefone}\n"
        f"*Endereco:* {cliente.endereco}\n"
        f"*Cidade:* {cliente.cidade}\n\n"
        f"*Data:* {agendamento.data_agendada.strftime('%d/%m/%Y')}\n"
        f"*Horario:* {agendamento.periodo}\n\n"
        f"*SERVICOS:*\n{itens_txt}\n\n"
        f"*VALOR TOTAL: {valor_total}*\n"
        f"*Orcamento: {orcamento.hash_id}*"
    )

    phones = [
        (os.environ.get("WHATSAPP_SOCIO_1") or Config.WHATSAPP_SOCIO_1).strip(),
        (os.environ.get("WHATSAPP_SOCIO_2") or Config.WHATSAPP_SOCIO_2).strip(),
    ]
    phones = [p for p in phones if p]

    if not phones:
        print("[WHATSAPP] Nenhum telefone configurado.")
        return {"status": "skipped"}

    results = {}
    for phone in phones:
        ok = _send_whatsapp(phone, mensagem)
        results[phone] = "sent" if ok else "failed"
        if not ok:
            # Loga a mensagem que seria enviada
            print(f"[WHATSAPP] FALHA ao enviar para {phone}. Configure META_WHATSAPP_TOKEN.")
            print(f"[WHATSAPP] Mensagem nao enviada:\n{mensagem}")

    return {"status": "completed", "results": results}
