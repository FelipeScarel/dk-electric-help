"""
Servico de notificacao WhatsApp para DK Electric Help.
Dispara mensagens automaticas para os socios quando um cliente agenda um servico.

Backends suportados:
- callmebot (recomendado, gratis): https://www.callmebot.com
- log (fallback): apenas imprime a mensagem no console
"""

import os
import urllib.request
import urllib.parse
import urllib.error

from config import Config


def _send_via_callmebot(phone: str, message: str, apikey: str) -> bool:
    """Envia mensagem via CallMeBot API (gratis)."""
    url = "https://api.callmebot.com/whatsapp.php"
    params = urllib.parse.urlencode({
        "phone": phone,
        "text": message,
        "apikey": apikey,
    })
    full_url = f"{url}?{params}"
    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "DK-Electric-Help/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            if "Message queued" in body or "Message sent" in body:
                return True
            print(f"[WHATSAPP] CallMeBot response: {body}")
            return False
    except urllib.error.URLError as e:
        print(f"[WHATSAPP] CallMeBot error for {phone}: {e}")
        return False


def _send_via_meta(phone: str, message: str, token: str, phone_id: str) -> bool:
    """Envia mensagem via Meta WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    import json
    data = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            print(f"[WHATSAPP] Meta API response for {phone}: {body}")
            return resp.status == 200
    except urllib.error.URLError as e:
        print(f"[WHATSAPP] Meta API error for {phone}: {e}")
        return False


def notify_scheduling(orcamento, agendamento) -> dict:
    """
    Notifica os socios via WhatsApp sobre um novo agendamento.
    Retorna dict com status para cada numero.
    """
    cliente = orcamento.cliente
    itens_desc = "\n".join(
        f"  • {i.descricao[:60]} - R$ {i.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        for i in orcamento.itens
    )

    mensagem = (
        f"*NOVO AGENDAMENTO - DK ELECTRIC HELP*\n\n"
        f"*Cliente:* {cliente.nome}\n"
        f"*Empresa:* {cliente.empresa or '---'}\n"
        f"*Telefone:* {cliente.telefone}\n"
        f"*Endereco:* {cliente.endereco}\n"
        f"*Cidade:* {cliente.cidade}\n\n"
        f"*Data:* {agendamento.data_agendada.strftime('%d/%m/%Y')}\n"
        f"*Horario:* {agendamento.periodo}\n\n"
        f"*Servicos:*\n{itens_desc}\n\n"
        f"*Valor Total:* R$ {orcamento.valor_total:,.2f}\n"
        f"*Orcamento:* {orcamento.hash_id}\n"
    ).replace(",", "X").replace(".", ",").replace("X", ".")

    phones = [
        os.environ.get("WHATSAPP_SOCIO_1") or Config.WHATSAPP_SOCIO_1,
        os.environ.get("WHATSAPP_SOCIO_2") or Config.WHATSAPP_SOCIO_2,
    ]
    phones = [p.strip() for p in phones if p and p.strip()]

    if not phones:
        print("[WHATSAPP] Nenhum telefone configurado. Mensagem nao enviada.")
        print(f"[WHATSAPP] Conteudo:\n{mensagem}")
        return {"status": "skipped", "reason": "no phones configured"}

    results = {}
    apikey = os.environ.get("CALLMEBOT_APIKEY", "").strip()
    meta_token = os.environ.get("META_WHATSAPP_TOKEN", "").strip()
    meta_phone_id = os.environ.get("META_WHATSAPP_PHONE_ID", "").strip()

    for phone in phones:
        success = False
        if apikey:
            success = _send_via_callmebot(phone, mensagem, apikey)
        if not success and meta_token and meta_phone_id:
            success = _send_via_meta(phone, mensagem, meta_token, meta_phone_id)
        if not success:
            print(f"[WHATSAPP] Falha ao enviar para {phone}. Backend nao configurado.")
            print(f"[WHATSAPP] Mensagem que seria enviada:\n{mensagem}")

        results[phone] = "sent" if success else "failed"

    return {"status": "completed", "results": results}
