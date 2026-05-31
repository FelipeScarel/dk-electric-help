"""
DK Electric Help - WhatsApp
Monta mensagem de agendamento e gera link wa.me.
Simples, sem API, sem dependencias.
"""

import urllib.parse


def notify_scheduling(orcamento, agendamento) -> str:
    """
    Monta a mensagem formatada e retorna URL-encoded pronta pro wa.me.
    """
    cliente = orcamento.cliente
    valor = f"R$ {orcamento.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    servicos = "\n".join(
        f"  - {i.descricao[:50]}: R$ {i.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        for i in orcamento.itens
    )
    obs = orcamento.observacoes.strip() if orcamento.observacoes else "Nenhuma"

    mensagem = (
        f"*NOVO AGENDAMENTO CONFIRMADO*\n\n"
        f"*Cliente:* {cliente.nome}\n"
        f"*Data:* {agendamento.data_agendada.strftime('%d/%m/%Y')}\n"
        f"*Hora:* {agendamento.periodo}\n\n"
        f"*Endereco:*\n{cliente.endereco}\n"
        f"*Cidade:* {cliente.cidade}\n"
        f"*Telefone:* {cliente.telefone}\n"
        + (f"*Empresa:* {cliente.empresa}\n" if cliente.empresa else "") +
        f"\n*Servicos:*\n{servicos}\n\n"
        f"*Valor Total:*\n{valor}\n\n"
        f"*Observacoes:*\n{obs}\n\n"
        f"*Orcamento:* {orcamento.hash_id}\n\n"
        f"_DK Electric Help - Engenharia Eletrica_"
    )

    return urllib.parse.quote(mensagem, safe="")
