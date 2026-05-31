"""
DK Electric Help - WhatsApp Notification
Playwright + sessao persistente = QR 1 vez, depois invisivel.
Sem Meta, sem token, sem API externa.
"""

import os
import time

from config import Config
from database import NotificationLog, db

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".wpp")


def _build_message(data: dict) -> str:
    return (
        f"*NOVO AGENDAMENTO*\n\n"
        f"Cliente: {data['cliente_nome']}\n"
        f"Data: {data['data']}\n"
        f"Hora: {data['hora']}\n\n"
        f"Endereco: {data['cliente_endereco']}\n"
        f"Cidade: {data['cliente_cidade']}\n"
        f"Telefone: {data['cliente_telefone']}\n"
        + (f"Empresa: {data['cliente_empresa']}\n" if data.get('cliente_empresa') else "") +
        f"\nServicos:\n{data['servicos']}\n\n"
        f"Valor: {data['valor']}\n\n"
        f"Obs: {data['obs']}\n\n"
        f"Orcamento: {data['hash_id']}"
    )


def notify_scheduling(data: dict, app=None) -> dict:
    """Envia WhatsApp via WhatsApp Web com sessao persistente."""
    from playwright.sync_api import sync_playwright

    phone = Config.WHATSAPP_NOTIFY.strip()
    mensagem = _build_message(data)
    os.makedirs(SESSION_DIR, exist_ok=True)

    first_time = not os.path.exists(os.path.join(SESSION_DIR, "Default"))

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            SESSION_DIR,
            headless=not first_time,
            viewport={"width": 960, "height": 800},
            args=["--no-sandbox"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        if first_time:
            print("[WPP] ====================================", flush=True)
            print("[WPP] PRIMEIRO USO - Escaneie o QR Code", flush=True)
            print("[WPP] WhatsApp > Aparelhos Conectados", flush=True)
            print("[WPP] Aguardando 90 segundos...", flush=True)
            print("[WPP] ====================================", flush=True)
            page.goto("https://web.whatsapp.com")
            page.wait_for_timeout(90000)
            context.close()
            print("[WPP] Sessao salva. Execute outro agendamento para testar.", flush=True)
            return {"status": "first_time"}

        # Headless = invisivel
        try:
            encoded = mensagem.replace("\n", "%0A").replace(" ", "%20").replace("#", "%23")
            url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded}"
            page.goto(url)
            page.wait_for_timeout(8000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

            print(f"[WPP] ENVIADO para {phone}", flush=True)

            if app:
                try:
                    with app.app_context():
                        log = NotificationLog(
                            agendamento_id=data.get("agendamento_id"), phone_to=phone,
                            status="sent", message_body=mensagem[:500],
                            response="ok", attempts=1,
                        )
                        db.session.add(log)
                        db.session.commit()
                except Exception as e:
                    print(f"[WPP] Erro log: {e}", flush=True)

            context.close()
            return {"status": "sent"}

        except Exception as e:
            print(f"[WPP] ERRO: {e}", flush=True)
            context.close()
            return {"status": "failed", "error": str(e)[:200]}
