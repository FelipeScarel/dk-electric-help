"""
DK Electric Help - WhatsApp
Monta mensagem profissional e gera link wa.me.
"""

import urllib.parse


def notify_scheduling(orcamento, agendamento) -> str:
    cliente = orcamento.cliente

    # Monta endereco completo
    endereco = cliente.endereco
    if cliente.numero:
        endereco += f", {cliente.numero}"
    if cliente.complemento:
        endereco += f" - {cliente.complemento}"
    if cliente.bairro:
        endereco += f" - {cliente.bairro}"

    cidade = cliente.cidade
    if cliente.estado:
        cidade += f" / {cliente.estado}"
    if cliente.cep:
        cidade += f" - CEP: {cliente.cep}"

    # Breakdown financeiro
    total_materiais = f"R$ {orcamento.total_materiais:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    total_mao_obra = f"R$ {orcamento.total_mao_obra:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_total = f"R$ {orcamento.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    mensagem = (
        f"\U0001F4C5 *NOVO AGENDAMENTO — DK ELECTRIC HELP*\n\n"
        f"\U0001F464 *Cliente:* {cliente.nome}\n"
        + (f"\U0001F3E2 *Empresa:* {cliente.empresa}\n" if cliente.empresa else "") +
        f"\U0001F4DE *Telefone:* {cliente.telefone}\n\n"
        f"\U0001F4C6 *Data:* {agendamento.data_agendada.strftime('%d/%m/%Y')}\n"
        f"\U0001F550 *Horario:* {agendamento.periodo}\n\n"
        f"\U0001F4CD *Endereco:*\n{endereco}\n"
        f"*Cidade:* {cidade}\n\n"
        f"\U0001F3F7 *Protocolo:* {orcamento.hash_id}\n"
        f"\U0001F4B0 *Total Materiais:* {total_materiais}\n"
        f"\U0001F527 *Total Mao de Obra:* {total_mao_obra}\n"
        f"\U0001F4B2 *Valor Total:* {valor_total}\n\n"
        f"_DK Electric Help | Tel: (19) 99624-5413_"
    )

    return urllib.parse.quote(mensagem, safe="")


def notify_approval(orcamento) -> str:
    """Monta mensagem de aprovacao — cliente aceitou o orcamento pelo PDF."""
    cliente = orcamento.cliente

    # Monta endereco completo
    endereco = cliente.endereco
    if cliente.numero:
        endereco += f", {cliente.numero}"
    if cliente.complemento:
        endereco += f" - {cliente.complemento}"
    if cliente.bairro:
        endereco += f" - {cliente.bairro}"

    cidade = cliente.cidade
    if cliente.estado:
        cidade += f" / {cliente.estado}"
    if cliente.cep:
        cidade += f" - CEP: {cliente.cep}"

    # Breakdown financeiro
    total_materiais = f"R$ {orcamento.total_materiais:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    total_mao_obra = f"R$ {orcamento.total_mao_obra:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_total = f"R$ {orcamento.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    mensagem = (
        f"\U0001F4CB *ORCAMENTO APROVADO — DK ELECTRIC HELP*\n\n"
        f"\U0001F464 *Cliente:* {cliente.nome}\n"
        + (f"\U0001F3E2 *Empresa:* {cliente.empresa}\n" if cliente.empresa else "") +
        f"\U0001F4DE *Telefone:* {cliente.telefone}\n\n"
        f"\U0001F4CD *Endereco:*\n{endereco}\n"
        f"*Cidade:* {cidade}\n\n"
        f"\U0001F3F7 *Protocolo:* {orcamento.hash_id}\n"
        f"\U0001F4B0 *Total Materiais:* {total_materiais}\n"
        f"\U0001F527 *Total Mao de Obra:* {total_mao_obra}\n"
        f"\U0001F4B2 *Valor Total:* {valor_total}\n\n"
        f"\U0001F4DD *Itens:*\n"
    )

    for item in orcamento.itens:
        vl = f"R$ {item.valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        mensagem += f"  - {item.descricao} (x{item.quantidade}): {vl}\n"

    mensagem += (
        f"\n_O cliente aceitou o orcamento e esta aguardando contato._\n"
        f"_DK Electric Help | Tel: (19) 99624-5413_"
    )

    return urllib.parse.quote(mensagem, safe="")
