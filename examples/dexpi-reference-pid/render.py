"""추출 결과를 원본 그림 위에 겹쳐 그린다."""
import sys, json, fitz

COLORS = dict(equipment=(0.8, 0, 0), symbol=(0, 0.4, 0.9), instrument=(0.6, 0, 0.7), nozzle=(0, 0.6, 0.6),
              arrow=(1, 0.5, 0), note=(0.5, 0.5, 0.5), mark=(0.7, 0.7, 0.7))

def main(svg_path, graph_path, out_png, clip=None, dpi=250):
    g = json.load(open(graph_path))
    src = fitz.open(svg_path)
    pdf = fitz.open('pdf', src.convert_to_pdf())
    page = pdf[0]
    sh = page.new_shape()
    for r in g['runs']:
        col = (0, 0.55, 0) if r['kind'] == 'pipe' else (0.1, 0.3, 1)
        pts = [fitz.Point(x, y) for x, y in r['coords']]
        sh.draw_polyline(pts)
        sh.finish(color=col, width=0.9, dashes='[1 1] 0' if r['gap'] else None, closePath=False)
    for n in g['nodes']:
        if n['role'] == 'mark':
            continue
        x0, y0, x1, y1 = n['bbox']
        sh.draw_rect(fitz.Rect(x0 - 0.8, y0 - 0.8, x1 + 0.8, y1 + 0.8))
        sh.finish(color=COLORS.get(n['role'], (0, 0, 0)), width=0.5)
    for j in g['junctions']:
        sh.draw_circle(fitz.Point(*j['pt']), 0.9)
        sh.finish(color=(0, 0, 0), fill=(1, 0.85, 0), width=0.3)
    for t in g['tables']:
        x0, y0, x1, y1 = t['bbox']
        sh.draw_rect(fitz.Rect(x0, y0, x1, y1)); sh.finish(color=(0.5, 0.5, 0.5), width=0.6, dashes='[2 1] 0')
    sh.commit()
    for n in g['nodes']:
        if n['role'] in ('mark', 'arrow') or n.get('attached_to'):
            continue
        x0, y0, x1, y1 = n['bbox']
        page.insert_text(fitz.Point(x0 - 0.5, y0 - 1.2), n['id'], fontsize=2.2, color=COLORS.get(n['role'], (0, 0, 0)))
    for j in g['junctions']:
        page.insert_text(fitz.Point(j['pt'][0] + 1.0, j['pt'][1] - 1.0), j['id'], fontsize=2.0, color=(0.4, 0.3, 0))
    rect = fitz.Rect(*clip) if clip else page.rect
    pix = page.get_pixmap(dpi=dpi, clip=rect)
    pix.save(out_png)
    print(out_png, pix.width, pix.height)

if __name__ == '__main__':
    clip = [float(v) for v in sys.argv[4].split(',')] if len(sys.argv) > 4 else None
    main(sys.argv[1], sys.argv[2], sys.argv[3], clip)
