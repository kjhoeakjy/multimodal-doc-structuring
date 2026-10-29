"""표본 입력과 처리 결과를 한 HTML 파일에 담는다. 실행: python app/build_page.py [표본 폴더] [출력 html]

표본 폴더는 input/(원본)과 output/<파일명>/result.json(처리 결과, run_all.py 또는 process.py 산출)을 가진 폴더.
"""
import os, sys, json, base64, io, math
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pipeline as pl
import raster_graph as rg

SOURCE = {'pid-standard': 'DEXPI 공개 예제', 'pid-plant': 'DEXPI 공개 예제', 'pid-lab': 'DEXPI 공개 예제', 'mech-flange': '합성', 'mech-iso': 'NIST 공개 도면',
          'faa-': 'FAA AC 43.13-1B', 'ko-': '합성', 'en-report': '합성', 'photo-': '공개 사진'}
QTAG = {'pid-standard-vector.svg': 'P4712', 'pid-standard-200dpi.png': 'T4750', 'pid-standard-scan.png': 'T4750', 'pid-plant-complex-vector.svg': 'P4712', 'pid-lab-vector.svg': 'P4712'}

def jpeg_uri(img, max_side, q):
    h, w = img.shape[:2]; s = min(1.0, max_side / max(h, w))
    if s < 1:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    ok, enc = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return 'data:image/jpeg;base64,' + base64.b64encode(enc.tobytes()).decode()

def view_image(src, R):
    """결과 좌표계와 같은 보기 그림을 다시 만듦(벡터는 150 dpi 렌더, 래스터는 축소·기울기 보정 후)."""
    ext = os.path.splitext(src)[1].lower()
    if R['kind'] == 'vector':
        import pymupdf
        doc = pymupdf.open(src); page = doc[0]; pix = page.get_pixmap(dpi=150)
        a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        return cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) if pix.n >= 3 else a[:, :, 0]
    if ext == '.pdf':
        import pymupdf
        pix = pymupdf.open(src)[0].get_pixmap(dpi=200); a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n); gray = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    else:
        gray = cv2.imread(src, cv2.IMREAD_GRAYSCALE)
    max_mp = R.get('plan', {}).get('max_mp', 12.0); H, W = gray.shape; mp = W * H / 1e6
    if mp > max_mp:
        s = math.sqrt(max_mp / mp); gray = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    if R['kind'] != 'photo':
        gray, _ = rg.deskew(gray)
    return gray

def main(folder, out_html):
    IN, OUT = os.path.join(folder, 'input'), os.path.join(folder, 'output')
    samples = []
    for f in sorted(os.listdir(IN)):
        rp = os.path.join(OUT, os.path.splitext(f)[0], 'result.json')
        if not os.path.exists(rp):
            continue
        R = json.load(open(rp, encoding='utf-8'))
        img = view_image(os.path.join(IN, f), R)
        vh, vw = img.shape
        if abs(vw - R['view']['w']) > 2 or abs(vh - R['view']['h']) > 2:
            print('크기 불일치', f, (vw, vh), (R['view']['w'], R['view']['h']))
        R['view']['w'], R['view']['h'] = vw, vh
        for k in ('labels', 'steps', 'svg', 'png', 'name', 'resources_after'):
            R.pop(k, None)
        src = next((v for k, v in SOURCE.items() if f.startswith(k)), '')
        samples.append(dict(name=f, source=src, qtag=QTAG.get(f), thumb=jpeg_uri(img, 400, 70), img=jpeg_uri(img, 2400, 78), R=R))
        print(f, R['kind'], f"{len(samples[-1]['img']) // 1024} KB")
    tpl = open(os.path.join(HERE, 'static', 'page.html'), encoding='utf-8').read()
    html = tpl.replace('/*__DATA__*/[]', json.dumps(samples, ensure_ascii=False, separators=(',', ':')))
    open(out_html, 'w', encoding='utf-8').write(html)
    print('wrote', out_html, f"{os.path.getsize(out_html) // 1024} KB", len(samples), 'samples')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'examples', 'sample-inputs'), sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '문서-구조화.html'))
