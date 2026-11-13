"""Paleta, fuentes y piezas comunes de las diapositivas.

Colores y fuentes de Surrealist (@surrealdb/ui 1.2.24), siempre planos: sin
degradados. Una sola cosa resaltada en violeta por imagen.
"""
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

BG = "0D0D12"       # fondo de diapositiva
CARD = "181721"     # caja
CARD_2 = "1F1D29"
LINE = "3B3948"     # borde fino
TEXT = "F5F5F7"
MUTED = "A19FAC"
VIOLET = "713DED"   # lo importante
LILAC = "CB63F9"    # segundo nivel
PINK = "FF00A0"     # fallo, alerta

SANS = "Geist"
MONO = "JetBrains Mono"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)
TOP = Inches(1.45)             # empieza la zona de imagen
BOTTOM = Inches(6.55)          # acaba la zona de imagen


def rgb(hex_):
    return RGBColor.from_string(hex_)


def background(slide):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(BG)


def text(slide, x, y, w, h, value, size=20, color=TEXT, font=SANS, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """Caja de texto sin borde. `value` puede tener varias líneas."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    for i, line in enumerate(value.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size = Pt(size)
        r.font.name = font
        r.font.bold = bold
        r.font.color.rgb = rgb(color)
    return tb


def frame(prs, number, title, keyline=None, notes=""):
    """Maqueta común: título arriba, zona de imagen, cifra clave y número abajo."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background(slide)
    if title:
        text(slide, MARGIN, Inches(0.5), W - 2 * MARGIN, Inches(0.7), title,
             size=32, bold=True)
    if keyline:
        text(slide, MARGIN, Inches(6.8), Inches(11), Inches(0.45), keyline,
             size=20, font=MONO)
    text(slide, W - MARGIN - Inches(0.6), Inches(6.88), Inches(0.6), Inches(0.3),
         f"{number:02d}", size=12, color=MUTED, font=MONO, align=PP_ALIGN.RIGHT)
    slide.notes_slide.notes_text_frame.text = notes.strip()
    return slide


def box(slide, x, y, w, h, label, accent=False, size=20, sub=None, font=SANS,
        fill=CARD):
    """Caja de diagrama: relleno plano, borde de 1 px, esquinas pequeñas."""
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shp.adjustments[0] = min(0.08, Inches(0.06) / min(w, h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(VIOLET if accent else fill)
    shp.line.color.rgb = rgb(VIOLET if accent else LINE)
    shp.line.width = Pt(1)
    shp.shadow.inherit = False
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for side in ("margin_left", "margin_right"):
        setattr(tf, side, Inches(0.12))
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size, r.font.name, r.font.bold = Pt(size), font, True
    r.font.color.rgb = rgb(TEXT)
    if sub:
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        r2.text = sub
        r2.font.size, r2.font.name = Pt(max(size - 4, 16)), MONO
        r2.font.color.rgb = rgb(TEXT if accent else MUTED)
    return shp


def arrow(slide, x1, y1, x2, y2, color=MUTED, head=True):
    """Línea recta fina con punta de flecha al final."""
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(1.5)
    if head:
        ln = c.line._get_or_add_ln()
        tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
        ln.append(tail)
    return c


def grid(slide, x, y, col_w, row_h, rows, header=True, size=18, first_col_bold=True,
         highlight_row=None):
    """Tabla dibujada con celdas planas: cabecera atenuada, líneas de 1 px."""
    for r, row in enumerate(rows):
        cx = x
        for c, cell in enumerate(row):
            w = col_w[c]
            shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx, y + r * row_h, w, row_h)
            shp.fill.solid()
            is_head = header and r == 0
            hl = highlight_row is not None and r == highlight_row
            shp.fill.fore_color.rgb = rgb(BG if is_head else (CARD_2 if hl else CARD))
            shp.line.color.rgb = rgb(VIOLET if hl else LINE)
            shp.line.width = Pt(1)
            shp.shadow.inherit = False
            tf = shp.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = tf.margin_right = Inches(0.12)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = cell
            run.font.size = Pt(size)
            run.font.name = SANS if (c == 0 or is_head) else SANS
            run.font.bold = is_head or (first_col_bold and c == 0)
            run.font.color.rgb = rgb(MUTED if is_head else TEXT)
            cx += w


def picture(slide, path, x=None, y=None, max_w=None, max_h=None):
    """Imagen escalada para caber en la zona de imagen, centrada."""
    from PIL import Image
    max_w = max_w or (W - 2 * MARGIN)
    max_h = max_h or (BOTTOM - TOP)
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(max_w / iw, max_h / ih)
    w, h = int(iw * scale), int(ih * scale)
    x = (W - w) // 2 if x is None else x
    y = TOP + (max_h - h) // 2 if y is None else y
    return slide.shapes.add_picture(str(path), Emu(x), Emu(y), Emu(w), Emu(h))
