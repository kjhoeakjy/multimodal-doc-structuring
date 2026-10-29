"""래스터 추출 결과를 원본 그림 위에 겹쳐 그린다."""
import sys, json, cv2
COL = dict(equipment=(0, 0, 200), symbol=(230, 100, 0), instrument=(180, 0, 150), nozzle=(150, 150, 0), note=(120, 120, 120))
def main(png, graph, out, scale=0.5):
    g = json.load(open(graph)); dpi = g.get('dpi', 300); k = dpi / 25.4
    im = cv2.cvtColor(cv2.imread(png, cv2.IMREAD_GRAYSCALE), cv2.COLOR_GRAY2BGR)
    for r in g['runs']:
        pts = [(int(x * k), int(y * k)) for x, y in r['coords']]
        col = (0, 140, 0) if r['kind'] == 'pipe' else (255, 80, 0)
        for a, b in zip(pts, pts[1:]):
            cv2.line(im, a, b, col, 3)
    for n in g['nodes']:
        if n['role'] == 'mark':
            continue
        x0, y0, x1, y1 = [int(v * k) for v in n['bbox']]
        cv2.rectangle(im, (x0 - 4, y0 - 4), (x1 + 4, y1 + 4), COL.get(n['role'], (0, 0, 0)), 2)
        cv2.putText(im, n['id'], (x0, max(10, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COL.get(n['role'], (0, 0, 0)), 1)
    for j in g['junctions']:
        cv2.circle(im, (int(j['pt'][0] * k), int(j['pt'][1] * k)), 8, (0, 200, 255), -1)
    for t in g['tables']:
        x0, y0, x1, y1 = [int(v * k) for v in t['bbox']]
        cv2.rectangle(im, (x0, y0), (x1, y1), (128, 128, 128), 2)
    if scale != 1:
        im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(out, im)
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.5)
