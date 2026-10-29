"""한글 합성 쪽 OCR 측정: 변형별 CER·토큰 정확도·시간, 탐지 저해상도·스레드 설정 비교"""
import json, sys, time, re, os
import numpy as np, cv2, torch

def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def reading_order(res):
    # res: [(box, text, conf)] -> 줄 묶음 후 좌→우
    items = sorted([(np.mean([p[1] for p in b]), min(p[0] for p in b), t, c, b) for b, t, c in res])
    lines, cur, ly = [], [], None
    for yc, x0, t, c, b in items:
        h = max(p[1] for p in b) - min(p[1] for p in b)
        if ly is None or abs(yc - ly) < h * 0.6: cur.append((x0, t)); ly = yc if ly is None else (ly + yc) / 2
        else: lines.append(cur); cur = [(x0, t)]; ly = yc
    if cur: lines.append(cur)
    return [' '.join(t for _, t in sorted(l)) for l in lines]

def norm(s): return re.sub(r'\s+', '', s)

def score(gt_lines, ocr_lines):
    g, o = norm(''.join(gt_lines)), norm(''.join(ocr_lines))
    cer = lev(g, o) / max(1, len(g))
    gtoks = set(t for s in gt_lines for t in s.split() if re.search(r'\d', t))
    otoks = set(t for s in ocr_lines for t in s.split())
    otext = norm(''.join(ocr_lines))
    hit = sum(1 for t in gtoks if norm(t) in otext)
    return dict(cer=round(cer, 4), chars=len(g), num_tokens=len(gtoks), num_tokens_hit=hit)

def main(d):
    import easyocr
    gt = [x['text'] for x in json.load(open(f'{d}/gt.json'))]
    reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
    out = {}
    def run(name, img, mode, threads=4, batch=8):
        torch.set_num_threads(threads)
        t0 = time.time()
        if mode == 'default':
            res = reader.readtext(img, batch_size=batch)
        else:  # 탐지 절반 해상도, 인식 원본
            small = cv2.resize(img, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
            t1 = time.time(); hl, fl = reader.detect(small); t_det = time.time() - t1
            hl = [[int(v * 2) for v in b] for b in hl[0]]; fl = [[[int(v * 2) for v in p] for p in b] for b in fl[0]]
            res = reader.recognize(img, horizontal_list=hl, free_list=fl, batch_size=batch)
        dt = time.time() - t0
        lines = reading_order(res)
        s = score(gt, lines); s.update(time_s=round(dt, 1), boxes=len(res), conf=round(float(np.mean([c for _, _, c in res])), 3) if res else 0, threads=threads, mode=mode)
        out[name] = s; print(name, s, flush=True)
        json.dump({'lines': lines}, open(f'{d}/{name}_ocr.json', 'w'), ensure_ascii=False, indent=1)
    for v in ['clean200', 'scan200', 'scan150', 'scan100']:
        img = cv2.imread(f'{d}/{v}.jpg', 0)
        run(v, img, 'default')
    img = cv2.imread(f'{d}/scan200.jpg', 0)
    run('scan200_det_half', img, 'half')
    run('scan200_threads1', img, 'default', threads=1)
    run('scan200_batch32', img, 'default', batch=32)
    json.dump(out, open(f'{d}/results.json', 'w'), ensure_ascii=False, indent=1)
if __name__ == '__main__': main(sys.argv[1] if len(sys.argv) > 1 else 'out')
