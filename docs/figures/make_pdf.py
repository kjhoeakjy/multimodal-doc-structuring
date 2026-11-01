#!/usr/bin/env python3
"""제출용 PDF. 슬라이드 SVG의 글자를 글꼴 윤곽선으로 바꿔, 어떤 PDF 보기 프로그램에서도 글꼴·굵기가 같게 보이게 한다.
실행: python make_pdf.py <출력 pdf>"""
import sys, os, re, html, subprocess, tempfile, shutil
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

HERE = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(HERE, '1장-도면-관계-구조화.svg')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
FILES = {('sans', False): os.path.join(HERE, 'fonts', 'WantedSans-Medium.ttf'), ('sans', True): os.path.join(HERE, 'fonts', 'WantedSans-Bold.ttf'),
         ('mono', False): 'C:/Windows/Fonts/consola.ttf', ('mono', True): 'C:/Windows/Fonts/consolab.ttf'}
_fonts, _paths = {}, {}

def font(key):
    if key not in _fonts:
        f = TTFont(FILES[key]); _fonts[key] = (f, f.getGlyphSet(), f.getBestCmap(), f['hmtx'], f['head'].unitsPerEm)
    return _fonts[key]

def glyph(key, ch):
    """문자 하나의 윤곽선(d)과 전진 폭. 고정폭 글꼴에 없는 한글은 같은 굵기의 Wanted Sans로 대체."""
    f, gs, cmap, hmtx, upm = font(key)
    if ord(ch) not in cmap and key[0] == 'mono':
        return glyph(('sans', key[1]), ch)
    name = cmap.get(ord(ch), '.notdef')
    k = (key, name)
    if k not in _paths:
        pen = SVGPathPen(gs); gs[name].draw(pen)
        _paths[k] = (pen.getCommands(), hmtx[name][0], upm)
    return _paths[k]

def outline(m):
    tag, body = m.group(1), html.unescape(m.group(2))
    a = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
    if 'transform' in a or 'Arial' in a.get('font-family', '') or 'text-anchor' not in a or 'font-size' not in a:   # 도면 안의 문자(Arial)는 그대로 둠
        return m.group(0)
    body = re.sub(r'\s+', ' ', body).strip()                               # 브라우저처럼 연속 공백을 한 칸으로
    size = float(a['font-size']); bold = a.get('font-weight') == '700'
    key = ('mono' if 'font-family' in a else 'sans', bold)
    gl = [glyph(key, c) for c in body]
    total = sum(adv * size / upm for _, adv, upm in gl)
    x = float(a['x']); y = float(a['y']); anc = a.get('text-anchor', 'start')
    x0 = x if anc == 'start' else (x - total / 2 if anc == 'middle' else x - total)
    parts, cx = [], x0
    for d, adv, upm in gl:
        s = size / upm
        if d:
            parts.append(f'<path transform="translate({cx:.2f} {y:.2f}) scale({s:.5f} {-s:.5f})" d="{d}"/>')
        cx += adv * s
    return f'<g fill="{a.get("fill", "#111111")}">' + ''.join(parts) + '</g>'

def main(out_pdf):
    svg = open(SVG, encoding='utf-8').read()
    svg = re.sub(r'<style>.*?</style>', '', svg, flags=re.S)          # 글꼴 정의는 더 이상 필요 없음
    svg = re.sub(r'(<text[^>]*>)(.*?)</text>', outline, svg, flags=re.S)
    tmp = tempfile.mkdtemp()
    page = os.path.join(tmp, 'p.html')
    open(page, 'w', encoding='utf-8').write('<!doctype html><html><head><meta charset="utf-8"><title>PT_AI_AX 개발_0014-000463</title>'
        '<style>@page{size:1600px 900px;margin:0}html,body{margin:0;padding:0}svg{display:block}</style></head><body>' + svg + '</body></html>')
    raw = os.path.join(tmp, 'p.pdf')
    subprocess.run([EDGE, '--headless', '--disable-gpu', '--no-pdf-header-footer', '--virtual-time-budget=3000',
                    f'--print-to-pdf={raw}', 'file:///' + page.replace('\\', '/')], capture_output=True, timeout=120)
    import pymupdf
    d = pymupdf.open(raw); m = d.metadata
    d.set_metadata({'title': 'PT_AI/AX 개발_0014-000463', 'author': '', 'subject': '', 'keywords': '', 'creator': '', 'producer': '',
                    'creationDate': m['creationDate'], 'modDate': m['modDate']})
    d.del_xml_metadata(); d.save(out_pdf, garbage=3, deflate=True); d.close()
    d = pymupdf.open(out_pdf); print('pages', d.page_count, 'fonts', d[0].get_fonts(), 'size', os.path.getsize(out_pdf))
    shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    main(sys.argv[1])
