"""
DK Electric Help - WhatsApp
Monta mensagem profissional e gera link wa.me.
"""

import urllib.parse


def notify_scheduling(orcamento, agendamento) -> str:
    cliente = orcamento.cliente

    mensagem = (
        f"✨ *NOVO AGENDAMENTO CONFIRMADO*\n\n"
        f"\U0001F464 *Cliente:* {cliente.nome}\n"
        + (f"\U0001F3E2 *Empresa:* {cliente.empresa}\n" if cliente.empresa else "") +
        f"\U0001F4DE *Telefone:* {cliente.telefone}\n\n"
        f"\U0001F4C5 *Data:* {agendamento.data_agendada.strftime('%d/%m/%Y')}\n"
        f"\U0001F550 *Horario:* {agendamento.periodo}\n\n"
        f"\U0001F4CD *Endereco:*\n{cliente.endereco}\n"
        f"*Cidade:* {cliente.cidade}\n\n"
        f"\U0001F3F7 *Protocolo:* {orcamento.hash_id}\n\n"
        f"_DK Electric Help - Engenharia Eletrica_"
    )

    return urllib.parse.quote(mensagem, safe="")
