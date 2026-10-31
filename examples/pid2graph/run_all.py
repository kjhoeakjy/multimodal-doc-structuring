"""PID2Graph 도면을 raster_graph.py로 처리해 정답과 대조한다.

사용: python run_all.py <PID2Graph 폴더> <출력 폴더> [--limit N] [--filter 문자열]
도면 폴더에서 PNG와 같은 이름의 graphml을 짝지어 처리한다. 해상도는 파일 메타데이터,
없으면 OCR 문자 상자 높이와 표준 용지 크기로 추정한다(app/pipeline.py와 같은 규칙).
결과: <출력 폴더>/<도면>/graph.json·eval.md, <출력 폴더>/결과.md
"""
import os, sys, json, time, glob, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'examples', 'public-documents', 'pid'))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import raster_graph as rg
import gt_from_graphml as gg
import evaluate as ev

def find_plans(root, flt):
    plans = []
    for png in sorted(glob.glob(os.path.join(root, '**', '*.png'), recursive=True)):
        stem = os.path.splitext(png)[0]
        gml = stem + '.graphml'
        if not os.path.exists(gml):
            cands = glob.glob(os.path.join(os.path.dirname(png), '*.graphml'))
            gml = next((c for c in cands if os.path.splitext(os.path.basename(c))[0] in os.path.basename(stem)), None)
        if gml and (not flt or flt in png):
            plans.append((png, gml))
    return plans

def ocr_and_dpi(png, out_prefix, reader):
    import cv2, pipeline as pl
    gray = cv2.imread(png, cv2.IMREAD_GRAYSCALE)
    H, W = gray.shape
    res = reader.readtext(gray, paragraph=False, min_size=4, text_threshold=0.6, low_text=0.3, mag_ratio=1.5)
    ocr_json = out_prefix + '_ocr.json'
    json.dump([[[[float(v) for v in p] for p in q], s, float(c)] for q, s, c in res], open(ocr_json, 'w'))
    texts = []
    for q, s, c in res:
        xs = [p[0] for p in q]; ys = [p[1] for p in q]
        texts.append(dict(text=s, conf=float(c), box=[min(xs), min(ys), max(xs), max(ys)]))
    dpi, how = pl.estimate_dpi(W, H, texts, pl.image_dpi(png))
    return ocr_json, dpi, how

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root'); ap.add_argument('out')
    ap.add_argument('--limit', type=int, default=0); ap.add_argument('--filter', default='')
    a = ap.parse_args()
    plans = find_plans(a.root, a.filter)
    if a.limit:
        plans = plans[:a.limit]
    os.makedirs(a.out, exist_ok=True)
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    rows = []
    for png, gml in plans:
        name = os.path.splitext(os.path.basename(png))[0]
        d = os.path.join(a.out, name); os.makedirs(d, exist_ok=True)
        t0 = time.time()
        try:
            truth = gg.convert(gml, os.path.join(d, 'truth.json'))
            ocr_json, dpi, how = ocr_and_dpi(png, os.path.join(d, name), reader)
            g = rg.main(png, dpi, os.path.join(d, name), ocr_json=ocr_json)
            gpath = os.path.join(d, 'graph.json')
            if not isinstance(g, dict):
                g = json.load(open(os.path.join(d, name) + '.json'))
            json.dump(g, open(gpath, 'w', encoding='utf-8'), ensure_ascii=False)
            r = ev.evaluate(gpath, os.path.join(d, 'truth.json'), dpi, os.path.join(d, 'eval.md'))
            r.update(name=name, secs=round(time.time() - t0, 1), dpi_how=how, classes=truth['classes'])
        except Exception as e:
            r = dict(name=name, error=repr(e), secs=round(time.time() - t0, 1))
        rows.append(r)
        json.dump(rows, open(os.path.join(a.out, '결과.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(json.dumps(r, ensure_ascii=False))
    ok = [r for r in rows if 'recall' in r]
    with open(os.path.join(a.out, '결과.md'), 'w', encoding='utf-8') as f:
        f.write("# PID2Graph 대조 결과\n\n| 도면 | 기호 | 대응 | 배관 정답 쌍 | 복원 | 재현율 | 추출 쌍 | 정답 밖 | 정밀도 | dpi | 초 |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in ok:
            f.write(f"| {r['name']} | {r['symbols']} | {r['symbols_matched']} | {r['gt_pipe_pairs']} | {r['hit']} | {r['recall']:.2f} | {r['ex_pipe_pairs']} | {r['extra']} | {r['precision']:.2f} | {r['dpi']} | {r['secs']} |\n")
        if ok:
            tp = sum(r['hit'] for r in ok); tg = sum(r['gt_pipe_pairs'] for r in ok)
            te = sum(r['ex_pipe_pairs'] for r in ok); tx = sum(r['extra'] for r in ok)
            f.write(f"\n도면 {len(ok)}장. 도면별 재현율 평균 {sum(r['recall'] for r in ok)/len(ok):.3f}, 합산 {tp}/{tg} = {tp/max(1,tg):.3f}. 합산 정밀도 {(te-tx)}/{te} = {(te-tx)/max(1,te):.3f}.\n")
        bad = [r for r in rows if 'error' in r]
        if bad:
            f.write("\n처리 실패: " + ", ".join(f"{r['name']}({r['error']})" for r in bad) + "\n")
    print('done', len(ok), 'ok', len(rows) - len(ok), 'failed')

if __name__ == '__main__':
    main()
