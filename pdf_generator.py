import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from config import Config

FONT_FAMILY = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

BLACK = colors.HexColor("#000000")
RED = colors.HexColor("#D60000")
WHITE = colors.white
LIGHT_BG = colors.HexColor("#f9f9f9")
BORDER = colors.HexColor("#e0e0e0")
GRAY = colors.HexColor("#555555")
GRAY_LIGHT = colors.HexColor("#999999")


def format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_date(dt):
    meses = ["", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    if isinstance(dt, datetime):
        return f"{dt.day:02d} de {meses[dt.month]} de {dt.year}"
    return str(dt)


def _draw_framed_box(c, x, y, w, h, line_width=1.5):
    """Desenha um retangulo elegante com borda preta fina."""
    c.setStrokeColor(BLACK)
    c.setLineWidth(line_width)
    c.rect(x, y, w, h, fill=0, stroke=1)


def _draw_section_header(c, y, text):
    """Faixa preta elegante como titulo de secao."""
    h = 20
    c.setFillColor(BLACK)
    c.rect(MARGIN, y - h + 2, CONTENT_W, h, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 9)
    c.drawString(MARGIN + 12, y - h + 7, text.upper())
    return y - h - 6


def _draw_header(c, y):
    """Cabecalho com logo + linha elegante."""
    logo_path = os.path.join(os.path.dirname(__file__), "static", "img", "Logo.png")

    logo_h = 45
    if os.path.exists(logo_path):
        from PIL import Image
        img = Image.open(logo_path)
        aspect = img.size[0] / img.size[1]
        logo_w = logo_h * aspect
        max_w = CONTENT_W * 0.50
        if logo_w > max_w:
            logo_w = max_w
            logo_h = max_w / aspect
        c.drawImage(logo_path, MARGIN, y - logo_h, width=logo_w, height=logo_h,
                     preserveAspectRatio=True, mask=None)
    else:
        c.setFont(FONT_BOLD, 20)
        c.setFillColor(BLACK)
        c.drawString(MARGIN, y - 10, "DK")
        c.setFillColor(RED)
        c.drawString(MARGIN + 36, y - 10, "ELECTRIC")
        c.setFillColor(BLACK)
        c.drawString(MARGIN + 138, y - 10, "HELP")

    # Info direita
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(BLACK)
    c.drawRightString(PAGE_W - MARGIN, y - 5, f"{Config.COMPANY_PHONE}")
    c.setFont(FONT_FAMILY, 7)
    c.setFillColor(GRAY)
    c.drawRightString(PAGE_W - MARGIN, y - 16, Config.COMPANY_EMAIL)

    # Linha preta
    y -= 35
    c.setStrokeColor(BLACK)
    c.setLineWidth(3)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)

    return y - 20


def _draw_client_section(c, y, orcamento):
    """Secao de dados do cliente em grid elegante."""
    cliente = orcamento.cliente

    # Monta endereco completo
    endereco_completo = cliente.endereco
    if cliente.numero:
        endereco_completo += f", {cliente.numero}"
    if cliente.complemento:
        endereco_completo += f" - {cliente.complemento}"
    if cliente.bairro:
        endereco_completo += f" - {cliente.bairro}"
    cidade_completa = cliente.cidade
    if cliente.estado:
        cidade_completa += f" / {cliente.estado}"

    fields = [
        ("CLIENTE", cliente.nome),
        ("EMPRESA", cliente.empresa or "---"),
        ("TELEFONE", cliente.telefone),
        ("CEP", cliente.cep or "---"),
        ("ENDERECO", endereco_completo),
        ("CIDADE", cidade_completa),
    ]

    rows = (len(fields) + 1) // 2
    box_h = rows * 28 + 20
    box_y = y - box_h

    c.setFillColor(LIGHT_BG)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.rect(MARGIN, box_y, CONTENT_W, box_h, fill=1, stroke=1)

    col_w = (CONTENT_W - 20) / 2
    x1 = MARGIN + 10
    x2 = x1 + col_w

    for idx, (label, value) in enumerate(fields):
        col = idx % 2
        row = idx // 2
        x = x1 if col == 0 else x2

        cy = y - 20 - row * 28
        c.setFont(FONT_BOLD, 7)
        c.setFillColor(RED)
        c.drawString(x, cy, label)
        c.setFont(FONT_FAMILY, 10)
        c.setFillColor(BLACK)
        # Trunca valor longo
        display_val = value if len(value) < 45 else value[:42] + "..."
        c.drawString(x, cy - 14, display_val)

        if row < rows - 1 or col == 0:
            c.setStrokeColor(BORDER)
            c.setLineWidth(0.3)
            c.line(x, cy - 20, x + col_w - 10, cy - 20)

    return box_y - 12


def _draw_items_section(c, y, orcamento):
    """Tabela de itens elegante e centralizada."""
    row_h = 20
    hdr_h = 18

    # Header
    c.setFillColor(BLACK)
    c.rect(MARGIN, y - hdr_h, CONTENT_W, hdr_h, fill=1, stroke=0)

    cols = [
        (MARGIN, 0.08, "ITEM", TA_CENTER),
        (MARGIN + CONTENT_W * 0.08, 0.44, "DESCRICAO", TA_LEFT),
        (MARGIN + CONTENT_W * 0.52, 0.08, "QTD", TA_CENTER),
        (MARGIN + CONTENT_W * 0.60, 0.20, "V. UNITARIO", TA_RIGHT),
        (MARGIN + CONTENT_W * 0.80, 0.20, "V. TOTAL", TA_RIGHT),
    ]

    c.setFont(FONT_BOLD, 8)
    c.setFillColor(WHITE)
    for x_start, w_frac, title, align in cols:
        w = CONTENT_W * w_frac
        if align == TA_CENTER:
            c.drawCentredString(x_start + w / 2, y - hdr_h + 5, title)
        elif align == TA_RIGHT:
            c.drawRightString(x_start + w - 8, y - hdr_h + 5, title)
        else:
            c.drawString(x_start + 6, y - hdr_h + 5, title)

    y -= hdr_h + 2

    # Linhas
    for idx, item in enumerate(orcamento.itens):
        cy = y - idx * row_h
        if idx % 2 == 1:
            c.setFillColor(LIGHT_BG)
            c.rect(MARGIN, cy - row_h + 2, CONTENT_W, row_h, fill=1, stroke=0)

        vals = [
            (item.item or "", TA_CENTER),
            (item.descricao[:60], TA_LEFT),
            (str(item.quantidade), TA_CENTER),
            (format_currency(item.valor_unitario), TA_RIGHT),
            (format_currency(item.valor_total), TA_RIGHT),
        ]

        c.setFont(FONT_FAMILY, 8)
        c.setFillColor(BLACK)
        for (val, align), (x_start, w_frac, _, _) in zip(vals, cols):
            w = CONTENT_W * w_frac
            if align == TA_CENTER:
                c.drawCentredString(x_start + w / 2, cy - 12, val)
            elif align == TA_RIGHT:
                c.drawRightString(x_start + w - 8, cy - 12, val)
            else:
                c.drawString(x_start + 6, cy - 12, val)

        c.setStrokeColor(BORDER)
        c.setLineWidth(0.2)
        c.line(MARGIN, cy - row_h + 2, PAGE_W - MARGIN, cy - row_h + 2)

    return y - len(orcamento.itens) * row_h - 14


def _draw_totals(c, y, orcamento):
    """Bloco de total elegante a direita."""
    box_w = CONTENT_W * 0.42
    box_x = PAGE_W - MARGIN - box_w
    box_h = 32

    c.setFillColor(LIGHT_BG)
    c.setStrokeColor(BLACK)
    c.setLineWidth(2)
    c.rect(box_x, y - box_h, box_w, box_h, fill=1, stroke=1)

    c.setFont(FONT_BOLD, 9)
    c.setFillColor(RED)
    c.drawString(box_x + 10, y - 14, "VALOR TOTAL")

    c.setFont(FONT_BOLD, 13)
    c.setFillColor(BLACK)
    c.drawRightString(box_x + box_w - 10, y - 14, format_currency(orcamento.valor_total))

    return y - box_h - 12


def _draw_terms(c, y):
    """Termos e condicoes em box elegante."""
    box_h = 68
    c.setFillColor(LIGHT_BG)
    c.setStrokeColor(BLACK)
    c.setLineWidth(1)
    c.rect(MARGIN, y - box_h, CONTENT_W, box_h, fill=1, stroke=1)

    # Barra lateral preta
    c.setFillColor(BLACK)
    c.rect(MARGIN, y - box_h, 4, box_h, fill=1, stroke=0)

    termos = [
        ("Condicoes:", FONT_BOLD, 8, BLACK),
        ("Precos validos ate a data de validade. Materiais conforme NR-10.", FONT_FAMILY, 7, GRAY),
        ("Mao de obra com engenheiro responsavel e ART registrada.", FONT_FAMILY, 7, GRAY),
        ("Pagamento: 50% no inicio, 50% na conclusao. Garantia de 12 meses.", FONT_FAMILY, 7, GRAY),
        ("Ao aprovar este orcamento, voce concorda com os termos acima.", FONT_FAMILY, 7, GRAY),
    ]

    ty = y - 16
    for text, font, size, color in termos:
        c.setFont(font, size)
        c.setFillColor(color)
        c.drawString(MARGIN + 16, ty, text)
        ty -= 12

    return y - box_h - 8


def _draw_approval_page(c, y, orcamento, approval_url):
    """Pagina de aprovacao elegante com botao clicavel."""

    # Box externo com borda grossa
    box_x = MARGIN + 20
    box_w = CONTENT_W - 40
    box_top = y
    box_bottom = MARGIN + 40

    _draw_framed_box(c, box_x, box_bottom, box_w, box_top - box_bottom, 2.5)

    inner_y = box_top - 45

    # Cabecalho da pagina
    c.setFont(FONT_BOLD, 16)
    c.setFillColor(BLACK)
    c.drawCentredString(PAGE_W / 2, inner_y, "PROTOCOLO DE APROVACAO")
    inner_y -= 28

    c.setFont(FONT_FAMILY, 10)
    c.setFillColor(GRAY)
    c.drawCentredString(PAGE_W / 2, inner_y, "Ao clicar no botao abaixo, voce confirma a aprovacao do")
    inner_y -= 16
    c.setFont(FONT_BOLD, 13)
    c.setFillColor(BLACK)
    c.drawCentredString(PAGE_W / 2, inner_y, f"Protocolo {orcamento.hash_id}")
    inner_y -= 16
    c.setFont(FONT_FAMILY, 10)
    c.setFillColor(GRAY)
    c.drawCentredString(PAGE_W / 2, inner_y, "e concorda com os termos e condicoes deste documento.")
    inner_y -= 40

    # Valor total
    c.setFont(FONT_BOLD, 20)
    c.setFillColor(BLACK)
    c.drawCentredString(PAGE_W / 2, inner_y, format_currency(orcamento.valor_total))
    inner_y -= 50

    # Botao vermelho
    btn_w = 300
    btn_h = 44
    btn_x = (PAGE_W - btn_w) / 2
    btn_y = inner_y - btn_h

    c.setFillColor(RED)
    c.roundRect(btn_x, btn_y, btn_w, btn_h, 5, fill=1, stroke=0)

    c.setFont(FONT_BOLD, 11)
    c.setFillColor(WHITE)
    c.drawCentredString(PAGE_W / 2, btn_y + btn_h / 2 - 5, "ACEITAR E AGENDAR SERVICO")

    c.linkURL(approval_url, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), thickness=0, color=None)

    inner_y = btn_y - 35

    c.setFont(FONT_FAMILY, 7)
    c.setFillColor(GRAY_LIGHT)
    c.drawCentredString(PAGE_W / 2, inner_y, "Voce sera redirecionado para escolher a data do servico.")
    inner_y -= 13
    c.drawCentredString(PAGE_W / 2, inner_y, f"Duvidas: {Config.COMPANY_PHONE} | {Config.COMPANY_EMAIL}")


def generate_orcamento_pdf(orcamento, output_path=None, base_url=None):
    if output_path is None:
        filename = f"orcamento_{orcamento.hash_id}.pdf"
        output_path = os.path.join(Config.PDF_OUTPUT_DIR, filename)

    if base_url is None:
        base_url = Config.BASE_URL
    approval_url = f"{base_url}validar-orcamento?id={orcamento.hash_id}"

    c = canvas.Canvas(output_path, pagesize=A4)
    c.setTitle(f"Protocolo DK {orcamento.hash_id}")
    c.setAuthor("DK Electric Help")
    c.setSubject(f"Orcamento {orcamento.hash_id}")

    # ========== PAGINA 1 ==========
    y = PAGE_H - MARGIN

    y = _draw_header(c, y)

    # Protocolo + datas
    c.setFont(FONT_BOLD, 13)
    c.setFillColor(BLACK)
    c.drawRightString(PAGE_W - MARGIN, y, f"PROTOCOLO {orcamento.hash_id}")
    y -= 14
    c.setFont(FONT_FAMILY, 7)
    c.setFillColor(GRAY_LIGHT)
    c.drawRightString(PAGE_W - MARGIN, y,
                      f"Emitido em {format_date(orcamento.data_emissao)}  |  "
                      f"Valido ate {format_date(orcamento.data_validade)}")
    y -= 22

    y = _draw_section_header(c, y, "Dados do Cliente")
    y = _draw_client_section(c, y, orcamento)
    y = _draw_section_header(c, y, "Itens do Orcamento")
    y = _draw_items_section(c, y, orcamento)
    y = _draw_totals(c, y, orcamento)
    y = _draw_terms(c, y)

    c.setFont(FONT_FAMILY, 6)
    c.setFillColor(GRAY_LIGHT)
    c.drawCentredString(PAGE_W / 2, MARGIN / 2, "DK Electric Help - Engenharia Eletrica | www.dkelectric.com.br")

    # ========== PAGINA 2 ==========
    c.showPage()
    y = PAGE_H - MARGIN
    _draw_approval_page(c, y, orcamento, approval_url)

    c.setFont(FONT_FAMILY, 6)
    c.setFillColor(GRAY_LIGHT)
    c.drawCentredString(PAGE_W / 2, MARGIN / 2, "DK Electric Help - Engenharia Eletrica | www.dkelectric.com.br")

    c.save()
    return output_path
