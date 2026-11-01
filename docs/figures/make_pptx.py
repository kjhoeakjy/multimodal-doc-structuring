#!/usr/bin/env python3
"""1장 슬라이드 SVG를 편집 가능한 PPTX 1장으로 옮긴다.
문자·사각형·선은 PowerPoint 도형으로, 도면 두 칸과 QR은 고해상도 그림으로 넣는다.
실행: python make_pptx.py <슬라이드 4배 PNG> <출력 pptx>"""
import sys, os, re, html
from xml.etree import ElementTree as ET
from PIL import Image
from fontTools.ttLib import TTFont
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn

HERE = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(HERE, '1장-도면-관계-구조화.svg')
W, H = 1600, 900
EMU = 12192000 / W                     # 13.333 in 너비 기준 1px
PT = 72 * 13.3333 / W                  # 1px = 0.6pt
NS = '{http://www.w3.org/2000/svg}'

def asc_ratio(path):
    f = TTFont(path); hh = f['hhea']; return hh.ascent / f['head'].unitsPerEm
ASC = {'sans': asc_ratio(os.path.join(HERE, 'fonts', 'WantedSans-Regular.ttf')), 'mono': asc_ratio('C:/Windows/Fonts/consola.ttf')}
sys.path.insert(0, HERE)

def rgb(c): return RGBColor.from_string(c.lstrip('#').upper())
def emu(v): return Emu(int(round(float(v) * EMU)))

def main(png4, out):
    src = open(SVG, encoding='utf-8').read()
    src = re.sub(r'<style>.*?</style>', '', src, flags=re.S)
    root = ET.fromstring(src)
    big = Image.open(png4); k = big.width / W
    prs = Presentation(); prs.slide_width = Emu(12192000); prs.slide_height = Emu(6858000)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    from make_slide import width as text_width   # 슬라이드 생성기와 같은 글자 폭 측정
    tmp = os.path.join(os.path.dirname(out), '_crop')
    os.makedirs(tmp, exist_ok=True)
    for i, e in enumerate(list(root)):
        tag = e.tag.replace(NS, '')
        a = e.attrib
        if tag == 'rect' and a.get('width') == str(W):
            continue
        if tag == 'svg':                 # 도면 칸·QR: 4배 렌더링에서 잘라 그림으로
            x, y, w, h = (float(a[t]) for t in ('x', 'y', 'width', 'height'))
            p = os.path.join(tmp, f'c{i}.png')
            big.crop((int(round(x * k)), int(round(y * k)), int(round((x + w) * k)), int(round((y + h) * k)))).save(p)
            s.shapes.add_picture(p, emu(x), emu(y), emu(w), emu(h))
        elif tag == 'rect':
            sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(a['x']), emu(a['y']), emu(a['width']), emu(a['height']))
            fill = a.get('fill', 'none'); stroke = a.get('stroke')
            if fill == 'none': sh.fill.background()
            else: sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
            if not stroke or stroke == 'none': sh.line.fill.background()
            else: sh.line.color.rgb = rgb(stroke); sh.line.width = Pt(float(a.get('stroke-width', 1)) * PT)
            sh.shadow.inherit = False
        elif tag == 'line':
            c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, emu(a['x1']), emu(a['y1']), emu(a['x2']), emu(a['y2']))
            c.line.color.rgb = rgb(a['stroke']); c.line.width = Pt(float(a.get('stroke-width', 1)) * PT)
            if a.get('marker-end'):
                ln = c.line._get_or_add_ln(); te = ln.makeelement(qn('a:tailEnd'), {'type': 'triangle', 'w': 'med', 'len': 'med'}); ln.append(te)
        elif tag == 'text':
            t = html.unescape(''.join(e.itertext()))
            size = float(a['font-size']); bold = a.get('font-weight') == '700'; mono = 'font-family' in a
            anchor = a.get('text-anchor', 'start')
            tw = text_width(t, size, bold, mono) * 1.12 + 6
            x = float(a['x']); y = float(a['y'])
            left = x if anchor == 'start' else (x - tw / 2 if anchor == 'middle' else x - tw)
            top = y - size * ASC['mono' if mono else 'sans']
            tb = s.shapes.add_textbox(emu(left), emu(top), emu(tw), emu(size * 1.4))
            tf = tb.text_frame; tf.word_wrap = False; tf.auto_size = None
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            tf.vertical_anchor = MSO_ANCHOR.TOP
            p = tf.paragraphs[0]; p.alignment = {'start': PP_ALIGN.LEFT, 'middle': PP_ALIGN.CENTER, 'end': PP_ALIGN.RIGHT}[anchor]
            r = p.add_run(); r.text = t
            f = r.font; f.size = Pt(size * PT); f.bold = bold; f.color.rgb = rgb(a.get('fill', '#111111'))
            FACE = 'Wanted Sans' if bold else 'Wanted Sans Medium'
            rPr = r._r.get_or_add_rPr()
            for el, face in (('a:latin', 'Consolas' if mono else FACE), ('a:ea', FACE), ('a:cs', FACE)):
                rPr.append(rPr.makeelement(qn(el), {'typeface': face}))
    cp = prs.core_properties
    cp.title = 'PT_AI/AX 개발_0014-000463'; cp.author = ''; cp.last_modified_by = ''; cp.comments = ''; cp.subject = ''; cp.keywords = ''
    prs.save(out)
    for f in os.listdir(tmp): os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
