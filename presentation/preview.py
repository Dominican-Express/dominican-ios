"""Previsualiza el .pptx en PNG sin PowerPoint y avisa de textos que no caben.

    uv run --with python-pptx --with pillow python presentation/preview.py [salida]

Aproximación: dibuja cajas, textos, flechas e imágenes con las mismas fuentes y
parte las líneas como lo haría PowerPoint. Sirve para cazar desbordes y solapes;
el visto bueno final se da abriendo el .pptx en PowerPoint.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn

HERE = Path(__file__).parent
FONTS = Path.home() / "Library" / "Fonts"
PX = 150  # píxeles por pulgada
EMU = 914400
FILES = {("Geist", False): "Geist-Regular.otf", ("Geist", True): "Geist-Bold.otf",
         ("JetBrains Mono", False): "JetBrainsMono-Regular.ttf",
         ("JetBrains Mono", True): "JetBrainsMono-Bold.ttf"}
_cache = {}


def px(emu):
    return int(round(emu / EMU * PX))


def font(name, bold, pt):
    key = (name, bold, pt)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(str(FONTS / FILES[(name or "Geist", bool(bold))]),
                                         int(round(pt / 72 * PX)))
    return _cache[key]


def wrap(draw, text, f, width):
    lines = []
    for raw in text.split("\n"):
        words, cur = raw.split(" "), ""
        for w in words:
            cand = (cur + " " + w).strip() if cur else w
            if draw.textlength(cand, font=f) <= width or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def draw_text(draw, shape, x, y, w, h, warn, label):
    tf = shape.text_frame
    ml, mr = px(tf.margin_left), px(tf.margin_right)
    mt, mb = px(tf.margin_top), px(tf.margin_bottom)
    blocks = []
    for p in tf.paragraphs:
        runs = p.runs
        if not runs:
            continue
        r = runs[0]
        f = font(r.font.name, r.font.bold, r.font.size.pt)
        color = "#" + str(r.font.color.rgb)
        txt = "".join(run.text for run in runs)
        for line in wrap(draw, txt, f, w - ml - mr):
            blocks.append((line, f, color, p.alignment, r.font.size.pt))
            if draw.textlength(line, font=f) > w - ml - mr + 2:
                warn.append(f"{label}: line wider than its box: {line!r}")
    total = sum(int(b[4] / 72 * PX * 1.2) for b in blocks)
    if total > h - mt - mb + 4:
        warn.append(f"{label}: text taller than its box ({total} > {h - mt - mb} px): "
                    f"{blocks[0][0]!r}")
    anchor = tf.vertical_anchor
    if anchor == MSO_ANCHOR.MIDDLE:
        cy = y + (h - total) // 2
    elif anchor == MSO_ANCHOR.BOTTOM:
        cy = y + h - mb - total
    else:
        cy = y + mt
    for line, f, color, align, pt in blocks:
        lw = draw.textlength(line, font=f)
        if align == PP_ALIGN.CENTER:
            lx = x + (w - lw) / 2
        elif align == PP_ALIGN.RIGHT:
            lx = x + w - mr - lw
        else:
            lx = x + ml
        draw.text((lx, cy), line, font=f, fill=color)
        cy += int(pt / 72 * PX * 1.2)


def render(slide, size, number):
    img = Image.new("RGB", size, "#" + str(slide.background.fill.fore_color.rgb))
    draw = ImageDraw.Draw(img)
    warn = []
    for shape in slide.shapes:
        label = f"slide {number}, {shape.name}"
        x, y = px(shape.left), px(shape.top)
        w, h = px(shape.width), px(shape.height)
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            from io import BytesIO
            pic = Image.open(BytesIO(shape.image.blob)).convert("RGB").resize((w, h))
            img.paste(pic, (x, y))
        elif shape.shape_type == MSO_SHAPE_TYPE.LINE or shape.shape_type is None and hasattr(shape, "begin_x"):
            x1, y1, x2, y2 = px(shape.begin_x), px(shape.begin_y), px(shape.end_x), px(shape.end_y)
            col = "#" + str(shape.line.color.rgb)
            draw.line((x1, y1, x2, y2), fill=col, width=3)
            if shape.line._get_or_add_ln().find(qn("a:tailEnd")) is not None:
                import math
                a = math.atan2(y2 - y1, x2 - x1)
                for d in (2.6, -2.6):
                    draw.line((x2, y2, x2 + 16 * math.cos(a + d), y2 + 16 * math.sin(a + d)),
                              fill=col, width=3)
        else:
            if shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
                fill = "#" + str(shape.fill.fore_color.rgb)
                line = "#" + str(shape.line.color.rgb)
                draw.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=fill, outline=line,
                                       width=2)
            if shape.has_text_frame and shape.text_frame.text.strip():
                draw_text(draw, shape, x, y, w, h, warn, label)
        if x < 0 or y < 0 or x + w > size[0] + 1 or y + h > size[1] + 1:
            warn.append(f"{label}: outside the slide")
    return img, warn


def main(out):
    prs = Presentation(HERE / "dominican-express.pptx")
    size = (px(prs.slide_width), px(prs.slide_height))
    out.mkdir(parents=True, exist_ok=True)
    warnings = []
    for i, slide in enumerate(prs.slides, 1):
        img, warn = render(slide, size, i)
        img.save(out / f"slide-{i:02d}.png")
        warnings += warn
    print(f"{len(prs.slides)} slides rendered to {out}")
    print("\n".join(warnings) if warnings else "no overflow warnings")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "preview")
