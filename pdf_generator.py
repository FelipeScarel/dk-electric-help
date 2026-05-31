import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import Config

# ---------------------------------------------------------------------------
# Estilos de paragrafo
# ---------------------------------------------------------------------------
FONT_FAMILY = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

PAGE_W, PAGE_H = A4  # 595.27 x 841.89 points
MARGIN = 2.5 * cm  # ~70.87pt
CONTENT_W = PAGE_W - 2 * MARGIN

# Preto: #000000, Vermelho: #D60000, Cinza: #555555, Cinza claro: #888888

STYLE_TITLE = ParagraphStyle("title", fontName=FONT_BOLD, fontSize=15, textColor=colors.HexColor("#000000"))
STYLE_TITLE_ACCENT = ParagraphStyle("title_accent", fontName=FONT_BOLD, fontSize=15, textColor=colors.HexColor("#D60000"))
STYLE_SUBTITLE = ParagraphStyle("subtitle", fontName=FONT_BOLD, fontSize=11, textColor=colors.HexColor("#000000"))
STYLE_BODY = ParagraphStyle("body", fontName=FONT_FAMILY, fontSize=9, textColor=colors.HexColor("#1a1a1a"), leading=13)
STYLE_BODY_BOLD = ParagraphStyle("body_b", fontName=FONT_BOLD, fontSize=9, textColor=colors.HexColor("#000000"), leading=13)
STYLE_BODY_RED = ParagraphStyle("body_red", fontName=FONT_BOLD, fontSize=9, textColor=colors.HexColor("#D60000"), leading=13)
STYLE_BODY_SMALL = ParagraphStyle("body_sm", fontName=FONT_FAMILY, fontSize=8, textColor=colors.HexColor("#555555"), leading=11)
STYLE_BODY_GRAY = ParagraphStyle("body_gray", fontName=FONT_FAMILY, fontSize=8, textColor=colors.HexColor("#888888"), leading=11)
STYLE_HEADER_INFO = ParagraphStyle("header_info", fontName=FONT_FAMILY, fontSize=8, textColor=colors.HexColor("#444444"), leading=12, alignment=TA_RIGHT)
STYLE_SECTION = ParagraphStyle("section", fontName=FONT_BOLD, fontSize=10, textColor=colors.white, leading=14)
STYLE_TH = ParagraphStyle("th", fontName=FONT_BOLD, fontSize=8, textColor=colors.white, leading=11)
STYLE_TD_LEFT = ParagraphStyle("td_l", fontName=FONT_FAMILY, fontSize=9, textColor=colors.HexColor("#1a1a1a"), leading=12)
STYLE_TD_CENTER = ParagraphStyle("td_c", fontName=FONT_FAMILY, fontSize=9, textColor=colors.HexColor("#1a1a1a"), leading=12, alignment=TA_CENTER)
STYLE_TD_RIGHT = ParagraphStyle("td_r", fontName=FONT_FAMILY, fontSize=9, textColor=colors.HexColor("#1a1a1a"), leading=12, alignment=TA_RIGHT)
STYLE_TD_BOLD = ParagraphStyle("td_b", fontName=FONT_BOLD, fontSize=9, textColor=colors.HexColor("#1a1a1a"), leading=12)
STYLE_APPROVAL_TITLE = ParagraphStyle("apprv_title", fontName=FONT_BOLD, fontSize=14, textColor=colors.HexColor("#000000"), leading=18, alignment=TA_CENTER)
STYLE_APPROVAL_BODY = ParagraphStyle("apprv_body", fontName=FONT_FAMILY, fontSize=10, textColor=colors.HexColor("#555555"), leading=15, alignment=TA_CENTER)
STYLE_APPROVAL_VALUE = ParagraphStyle("apprv_value", fontName=FONT_BOLD, fontSize=16, textColor=colors.HexColor("#000000"), leading=20, alignment=TA_CENTER)
STYLE_FOOTER = ParagraphStyle("footer", fontName=FONT_FAMILY, fontSize=7, textColor=colors.HexColor("#888888"), alignment=TA_CENTER)

BLACK = colors.HexColor("#000000")
RED = colors.HexColor("#D60000")
WHITE = colors.white
LIGHT_GRAY = colors.HexColor("#f7f7f7")
BORDER_GRAY = colors.HexColor("#e0e0e0")


def format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_date(dt):
    meses = [
        "", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    if isinstance(dt, datetime):
        return f"{dt.day:02d} de {meses[dt.month]} de {dt.year}"
    return str(dt)


def _draw_section_header(c, y, text):
    """Desenha uma faixa preta com texto branco como titulo de secao."""
    c.setFillColor(BLACK)
    c.rect(MARGIN, y - 14, CONTENT_W, 22, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 10)
    c.drawString(MARGIN + 10, y - 9, text.upper())
    return y - 30


def _draw_header(c, y):
    """Desenha cabecalho profissional com logo proporcional e info de contato."""
    logo_path = os.path.join(os.path.dirname(__file__), "static", "img", "Logo.png")

    # Logo com altura fixa e largura proporcional
    logo_h = 50
    if os.path.exists(logo_path):
        from PIL import Image
        img = Image.open(logo_path)
        img_w, img_h = img.size
        aspect = img_w / img_h
        logo_w = logo_h * aspect
        # Limita largura maxima
        max_w = CONTENT_W * 0.55
        if logo_w > max_w:
            logo_w = max_w
            logo_h = max_w / aspect
        c.drawImage(logo_path, MARGIN, y - logo_h, width=logo_w, height=logo_h,
                     preserveAspectRatio=True, mask=None)
    else:
        # Fallback: texto DK ELECTRIC HELP
        c.setFont(FONT_BOLD, 22)
        c.setFillColor(BLACK)
        c.drawString(MARGIN, y - 12, "DK")
        c.setFillColor(RED)
        c.drawString(MARGIN + 40, y - 12, "ELECTRIC")
        c.setFillColor(BLACK)
        c.drawString(MARGIN + 148, y - 12, "HELP")

    # Info de contato a direita
    c.setFont(FONT_BOLD, 9)
    c.setFillColor(BLACK)
    c.drawRightString(PAGE_W - MARGIN, y - 8, f"Contato: {Config.COMPANY_PHONE}")
    c.setFont(FONT_FAMILY, 8)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawRightString(PAGE_W - MARGIN, y - 22, f"E-mail: {Config.COMPANY_EMAIL}")
    c.setFont(FONT_FAMILY, 7)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawRightString(PAGE_W - MARGIN, y - 34, "Engenharia Eletrica de Precisao")

    # Linha preta grossa abaixo do cabecalho
    c.setStrokeColor(BLACK)
    c.setLineWidth(2.5)
    c.line(MARGIN, y - 50, PAGE_W - MARGIN, y - 50)

    return y - 68


def _draw_client_grid(c, y, orcamento):
    """Desenha grid de dados do cliente."""
    cliente = orcamento.cliente
    fields = [
        ("Cliente:", cliente.nome),
        ("Empresa:", cliente.empresa or "---"),
        ("Telefone:", cliente.telefone),
        ("Endereco:", cliente.endereco),
        ("Cidade:", cliente.cidade),
    ]

    col_w = CONTENT_W / 2
    row_h = 16
    x1 = MARGIN
    x2 = MARGIN + col_w

    for idx, (label, value) in enumerate(fields):
        col = idx % 2
        row_offset = (idx // 2) * row_h
        x = x1 if col == 0 else x2

        # Label em vermelho
        c.setFont(FONT_BOLD, 9)
        c.setFillColor(RED)
        c.drawString(x, y - row_offset, label)
        # Valor em preto
        c.setFont(FONT_FAMILY, 9)
        c.setFillColor(colors.HexColor("#1a1a1a"))
        c.drawString(x + 65, y - row_offset, value)
        # Linha inferior
        c.setStrokeColor(BORDER_GRAY)
        c.setLineWidth(0.5)
        c.line(x, y - row_offset - 5, x + col_w - 10, y - row_offset - 5)

    return y - ((len(fields) + 1) // 2) * row_h - 5


def _draw_items_table(c, y, orcamento):
    """Desenha tabela de itens com cabecalho vermelho."""
    row_h = 18
    header_h = 16
    col_widths = [0.08, 0.42, 0.08, 0.21, 0.21]
    headers = ["ITEM", "DESCRICAO", "QTD", "VALOR UNIT.", "VALOR TOTAL"]
    aligns = [TA_LEFT, TA_LEFT, TA_CENTER, TA_RIGHT, TA_RIGHT]

    # Cabecalho da tabela
    x_pos = MARGIN
    c.setFillColor(RED)
    c.rect(MARGIN, y - header_h, CONTENT_W, header_h, fill=1, stroke=0)
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(WHITE)
    for i, (header, w_frac) in enumerate(zip(headers, col_widths)):
        w = CONTENT_W * w_frac
        c.drawString(x_pos + 6, y - header_h + 4, header)
        x_pos += w

    y -= header_h + 2

    # Linhas de dados
    for idx, item in enumerate(orcamento.itens):
        row_y = y - idx * row_h
        bg = LIGHT_GRAY if idx % 2 == 1 else WHITE
        c.setFillColor(bg)
        c.rect(MARGIN, row_y - row_h + 2, CONTENT_W, row_h - 1, fill=1, stroke=0)

        # Linha divisoria
        c.setStrokeColor(BORDER_GRAY)
        c.setLineWidth(0.3)
        c.line(MARGIN, row_y - row_h + 2, PAGE_W - MARGIN, row_y - row_h + 2)

        x_pos = MARGIN
        values = [
            (item.item or "", STYLE_TD_BOLD, TA_LEFT),
            (item.descricao, STYLE_TD_LEFT, TA_LEFT),
            (str(item.quantidade), STYLE_TD_CENTER, TA_CENTER),
            (format_currency(item.valor_unitario), STYLE_TD_RIGHT, TA_RIGHT),
            (format_currency(item.valor_total), STYLE_TD_RIGHT, TA_RIGHT),
        ]
        c.setFillColor(colors.HexColor("#1a1a1a"))
        for (val, style, _), w_frac in zip(values, col_widths):
            w = CONTENT_W * w_frac
            x_text = x_pos + 6
            if style.alignment == TA_RIGHT:
                x_text = x_pos + w - 10
            elif style.alignment == TA_CENTER:
                x_text = x_pos + w / 2

            c.setFont(style.fontName, style.fontSize)
            c.drawString(x_text, row_y - 12, val)
            x_pos += w

    return y - len(orcamento.itens) * row_h - 8


def _draw_total(c, y, valor_total):
    """Desenha o valor total alinhado a direita."""
    box_w = CONTENT_W * 0.40
    box_x = PAGE_W - MARGIN - box_w
    box_h = 28

    c.setStrokeColor(BLACK)
    c.setLineWidth(2)
    c.line(box_x, y, box_x + box_w, y)

    c.setFont(FONT_BOLD, 10)
    c.setFillColor(RED)
    c.drawString(box_x, y - 16, "VALOR TOTAL")

    c.setFont(FONT_BOLD, 11)
    c.setFillColor(BLACK)
    c.drawRightString(box_x + box_w, y - 16, format_currency(valor_total))

    return y - 35


def _draw_terms(c, y):
    """Desenha secao de termos e condicoes."""
    box_h = 80
    c.setFillColor(LIGHT_GRAY)
    c.rect(MARGIN, y - box_h, CONTENT_W, box_h, fill=1, stroke=0)
    c.setStrokeColor(BLACK)
    c.setLineWidth(3)
    c.line(MARGIN, y, MARGIN, y - box_h)

    termos = [
        ("Condicoes e Termos:", "Helvetica-Bold", 8, BLACK),
        ("Precos validos ate a data de validade indicada neste orcamento.", "Helvetica", 7, colors.HexColor("#555555")),
        ("Materiais de primeira linha conforme normas ABNT NR-10.", "Helvetica", 7, colors.HexColor("#555555")),
        ("Mao de obra inclui engenheiro responsavel com ART registrada.", "Helvetica", 7, colors.HexColor("#555555")),
        ("Pagamento: 50% no inicio, 50% na conclusao do servico.", "Helvetica", 7, colors.HexColor("#555555")),
        ("Garantia de 12 meses sobre os servicos executados.", "Helvetica", 7, colors.HexColor("#555555")),
        ("Ao aprovar este orcamento, voce concorda com os termos acima.", "Helvetica", 7, colors.HexColor("#555555")),
    ]
    ty = y - 14
    for text, font, size, color in termos:
        c.setFont(font, size)
        c.setFillColor(color)
        c.drawString(MARGIN + 14, ty, text)
        ty -= 12

    return y - box_h - 8


def _draw_approval_page(c, y, orcamento, approval_url):
    """Desenha a pagina de aprovacao com o botao clicavel."""

    # Titulo da secao
    box_x = MARGIN + 30
    box_w = CONTENT_W - 60
    box_top = y
    box_bottom = MARGIN + 60

    # Borda preta grossa
    c.setStrokeColor(BLACK)
    c.setLineWidth(2.5)
    c.rect(box_x, box_bottom, box_w, box_top - box_bottom, fill=0, stroke=1)

    inner_y = box_top - 40

    # Titulo
    c.setFont(FONT_BOLD, 18)
    c.setFillColor(BLACK)
    c.drawCentredString(PAGE_W / 2, inner_y, "CONTRATO DE SERVICO")
    inner_y -= 30

    # Texto descritivo
    c.setFont(FONT_FAMILY, 11)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawCentredString(PAGE_W / 2, inner_y, "Ao clicar no botao abaixo, voce aprova o")
    inner_y -= 18
    c.setFont(FONT_BOLD, 12)
    c.setFillColor(BLACK)
    c.drawCentredString(PAGE_W / 2, inner_y, f"Orcamento {orcamento.hash_id}")
    inner_y -= 18
    c.setFont(FONT_FAMILY, 11)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawCentredString(PAGE_W / 2, inner_y, "e concorda com os termos e condicoes deste documento.")
    inner_y -= 35

    # Valor
    c.setFont(FONT_BOLD, 22)
    c.setFillColor(BLACK)
    c.drawCentredString(PAGE_W / 2, inner_y, format_currency(orcamento.valor_total))
    inner_y -= 45

    # BOTAO CLICAVEL (retangulo vermelho)
    btn_w = 320
    btn_h = 42
    btn_x = (PAGE_W - btn_w) / 2
    btn_y = inner_y - btn_h

    c.setFillColor(RED)
    c.roundRect(btn_x, btn_y, btn_w, btn_h, 4, fill=1, stroke=0)

    # Texto do botao
    c.setFont(FONT_BOLD, 12)
    c.setFillColor(WHITE)
    c.drawCentredString(PAGE_W / 2, btn_y + btn_h / 2 - 5, "ACEITAR ORCAMENTO E AGENDAR SERVICO")
    c.drawCentredString(PAGE_W / 2, btn_y + btn_h / 2 - 18, "→")  # seta

    # LINK CLICAVEL (anotacao sobre o botao)
    c.linkURL(approval_url, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), thickness=0, color=None)

    inner_y = btn_y - 35

    # Nota de rodape
    c.setFont(FONT_FAMILY, 8)
    c.setFillColor(colors.HexColor("#999999"))
    c.drawCentredString(PAGE_W / 2, inner_y, "Voce sera redirecionado para agendar a data de execucao do servico.")
    inner_y -= 14
    c.drawCentredString(PAGE_W / 2, inner_y, f"Duvidas? Entre em contato: {Config.COMPANY_PHONE}")


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------

def generate_orcamento_pdf(orcamento, output_path=None, base_url=None):
    if output_path is None:
        filename = f"orcamento_{orcamento.hash_id}.pdf"
        output_path = os.path.join(Config.PDF_OUTPUT_DIR, filename)

    if base_url is None:
        base_url = Config.BASE_URL
    approval_url = f"{base_url}validar-orcamento?id={orcamento.hash_id}"

    c = canvas.Canvas(output_path, pagesize=A4)
    c.setTitle(f"Orcamento DK {orcamento.hash_id}")
    c.setAuthor("DK Electric Help")

    # ==================== PAGINA 1 ====================
    y = PAGE_H - MARGIN

    # Cabecalho
    y = _draw_header(c, y)

    # Numero do orcamento e datas
    c.setFont(FONT_BOLD, 14)
    c.setFillColor(BLACK)
    c.drawRightString(PAGE_W - MARGIN, y, f"ORCAMENTO Nº {orcamento.hash_id}")
    y -= 16
    c.setFont(FONT_FAMILY, 8)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawRightString(PAGE_W - MARGIN, y,
                      f"Emitido em {format_date(orcamento.data_emissao)} — Valido ate {format_date(orcamento.data_validade)}")
    y -= 30

    # Secao: Dados do Cliente
    y = _draw_section_header(c, y, "Dados do Cliente")
    y = _draw_client_grid(c, y, orcamento)

    # Secao: Itens do Orcamento
    y -= 8
    y = _draw_section_header(c, y, "Itens do Orcamento")
    y = _draw_items_table(c, y, orcamento)

    # Valor Total
    y = _draw_total(c, y, orcamento.valor_total)

    # Termos e condicoes
    y -= 10
    y = _draw_terms(c, y)

    # Rodape da pagina 1
    c.setFont(FONT_FAMILY, 7)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawCentredString(PAGE_W / 2, MARGIN / 2, "DK Electric Help - Engenharia Eletrica de Precisao")

    # ==================== PAGINA 2: APROVACAO ====================
    c.showPage()
    y = PAGE_H - MARGIN
    _draw_approval_page(c, y, orcamento, approval_url)

    c.setFont(FONT_FAMILY, 7)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawCentredString(PAGE_W / 2, MARGIN / 2, "DK Electric Help - Engenharia Eletrica de Precisao")

    c.save()
    return output_path
